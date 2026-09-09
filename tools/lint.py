#!/usr/bin/env python3
"""Vault linter for the AI / Robotics / Startups knowledge base.

Deterministic checks only — this script never edits notes. It is the machine-checkable
half of `meta/schema.md`. See `meta/agent-instructions.md` for how it fits the pipeline.

Usage:
    python tools/lint.py                 # lint the whole vault
    python tools/lint.py companies/X.md  # lint specific files (index still built from all)
    python tools/lint.py --strict        # warnings also fail the run
    python tools/lint.py --no-report     # don't write meta/health/lint-report.md

Exit code: 1 if any errors (or, with --strict, any warnings), else 0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# --------------------------------------------------------------------------- model

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    path: str
    severity: str
    rule: str
    message: str
    line: int | None = None

    def format(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"  {self.severity:7} {self.rule:26} {loc}\n          {self.message}"


@dataclass
class Note:
    path: Path
    rel: str
    fm: dict
    body: str
    fm_error: str | None = None

    @property
    def type(self) -> str | None:
        t = self.fm.get("type")
        return t if isinstance(t, str) else None

    @property
    def is_seed(self) -> bool:
        return bool(self.fm.get("seed"))

    @property
    def stem(self) -> str:
        return self.path.stem

    def names(self) -> set[str]:
        out = {self.stem.lower()}
        name = self.fm.get("name")
        if isinstance(name, str) and name.strip():
            out.add(name.strip().lower())
        aliases = self.fm.get("aliases")
        if isinstance(aliases, list):
            out.update(str(a).strip().lower() for a in aliases if str(a).strip())
        return out

    def sections(self) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", self.body, re.M)]


# --------------------------------------------------------------------------- schema

@dataclass
class Schema:
    required: list[str]
    enums: dict[str, set[str]] = field(default_factory=dict)
    list_enums: dict[str, set[str]] = field(default_factory=dict)
    list_fields: list[str] = field(default_factory=list)   # must be a YAML list (any values)
    full_dates: list[str] = field(default_factory=list)   # YYYY-MM-DD
    year_dates: list[str] = field(default_factory=list)    # YYYY | YYYY-MM | YYYY-MM-DD
    sections: list[str] = field(default_factory=list)


SCHEMAS: dict[str, Schema] = {
    "concept": Schema(
        required=["type", "name", "category", "maturity", "created", "updated"],
        enums={
            "category": {"protocol", "architecture", "technique", "infra", "eval",
                         "primitive", "pattern"},
            "maturity": {"emerging", "established", "contested", "fading"},
        },
        full_dates=["created", "updated"],
        sections=["Definition", "How it works", "Why it matters"],
    ),
    "company": Schema(
        required=["type", "name", "status", "sectors", "watchlist", "created", "updated"],
        enums={
            "status": {"active", "stealth", "acquired", "shut-down"},
            "stage": {"pre-seed", "seed", "series-a", "series-b", "series-c",
                      "series-d+", "public", "bootstrapped"},
            "priority": {"high", "medium", "low"},
        },
        list_fields=["sectors"],
        full_dates=["created", "updated"],
        year_dates=["founded"],
        sections=["Summary", "What they do", "Timeline"],
    ),
    "person": Schema(
        required=["type", "name", "created", "updated"],
        full_dates=["created", "updated"],
        sections=["Summary", "Timeline"],
    ),
    "technology": Schema(
        required=["type", "name", "category", "status", "first_seen", "maturity",
                  "created", "updated"],
        enums={
            "category": {"model", "hardware", "robot", "framework", "benchmark"},
            "status": {"announced", "released", "deprecated", "vaporware"},
            "maturity": {"emerging", "scaling", "mainstream", "superseded"},
        },
        full_dates=["created", "updated", "first_seen"],
        sections=["What it is", "Why it matters", "Timeline"],
    ),
    "moc": Schema(
        required=["type", "name", "kind", "created", "updated"],
        enums={"kind": {"thread", "index"}},
        list_enums={"domains": {"ai", "robotics", "hardware/compute", "business"}},
        list_fields=["domains"],
        full_dates=["created", "updated"],
        sections=[],  # thread sections checked separately
    ),
    "source": Schema(
        required=["type", "title", "publication", "published", "accessed", "url", "tier"],
        enums={"tier": {"primary", "secondary", "tertiary"}},
        full_dates=["published", "accessed"],
        sections=["Extract"],
    ),
}

# types that may appear but get only structural checks (valid frontmatter, links)
LOOSE_TYPES = {"meta", "dashboard"}

KNOWN_SECTORS = {
    "foundation-models", "ai-applications", "ai-infra", "ai-tooling", "ai-agents",
    "robotics", "humanoid", "industrial-robotics", "mobile-robotics", "robot-learning",
    "autonomy", "semiconductors", "ai-hardware", "data-center", "edge-compute",
    "simulation",
}

VOLATILE_COMPANY_FIELDS = ["total_funding_usd", "last_round", "stage"]

# only files under these top-level dirs are linted (others may still be link targets)
LINT_DIRS = {"concepts", "companies", "people", "technologies", "topics", "sources",
             "inbox", "digests", "dashboards", "meta"}
SKIP_DIRS = {".git", ".obsidian", ".venv", "tools", "templates", "node_modules",
             ".pytest_cache", "__pycache__"}

FULL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YEAR_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
DATED_BULLET_RE = re.compile(r"^\s*-\s+(\d{4}-\d{2}-\d{2})\s+[—-]")


# --------------------------------------------------------------------------- loading

def split_frontmatter(text: str) -> tuple[str | None, str]:
    m = re.match(r"^---\n(.*?)\n---[ \t]*\n?(.*)$", text, re.DOTALL)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def load_note(path: Path, root: Path) -> Note:
    rel = str(path.relative_to(root))
    text = path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        return Note(path, rel, {}, body, fm_error="no frontmatter block")
    try:
        data = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        return Note(path, rel, {}, body, fm_error=f"YAML parse error: {e}")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return Note(path, rel, {}, body, fm_error="frontmatter is not a mapping")
    return Note(path, rel, data, body)


def iter_markdown(root: Path):
    for p in sorted(root.rglob("*.md")):
        parts = p.relative_to(root).parts
        if parts[0] in SKIP_DIRS:
            continue
        yield p


def top_dir(rel: str) -> str:
    return Path(rel).parts[0]


# --------------------------------------------------------------------------- helpers

def is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def wikilink_targets(text: str) -> list[tuple[str, int]]:
    """Return (target, line_number) for every [[wikilink]] (alias/heading stripped).

    Links inside fenced code blocks and inline `code` spans are ignored — in the docs
    those are illustrative, not real links.
    """
    out = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        marker = line.lstrip()
        if marker.startswith("```") or marker.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        no_code = re.sub(r"`[^`]*`", "", line)
        for m in WIKILINK_RE.finditer(no_code):
            raw = m.group(1)
            target = raw.split("|")[0].split("#")[0].strip()
            if target:
                out.append((target, i))
    return out


def resolve_key(target: str) -> str:
    """Normalise a wikilink target to an index key."""
    t = target.strip().lower()
    if "/" in t:
        t = t.rsplit("/", 1)[1]
    if t.endswith(".md"):
        t = t[:-3]
    return t


def prose_length(body: str) -> int:
    stripped = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    stripped = re.sub(r"^#+ .*$", "", stripped, flags=re.M)          # headings
    stripped = re.sub(r"^```.*?^```", "", stripped, flags=re.M | re.DOTALL)  # code
    stripped = re.sub(r"^\s*[-*]\s*$", "", stripped, flags=re.M)      # empty bullets
    return len(stripped.strip())


def section_body(body: str, heading: str) -> str:
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(^##\s|\Z)", body,
                  re.M | re.DOTALL)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- checks

def check_frontmatter(note: Note) -> list[Finding]:
    if note.fm_error:
        return [Finding(note.rel, ERROR, "frontmatter-invalid", note.fm_error)]
    if not note.type:
        return [Finding(note.rel, ERROR, "missing-type", "no `type` in frontmatter")]
    if note.type not in SCHEMAS and note.type not in LOOSE_TYPES:
        return [Finding(note.rel, ERROR, "unknown-type",
                        f"type `{note.type}` is not in the schema")]
    return []


def check_schema(note: Note) -> list[Finding]:
    schema = SCHEMAS.get(note.type)
    if schema is None:
        return []
    out: list[Finding] = []

    for fld in schema.required:
        if fld not in note.fm or is_empty(note.fm[fld]):
            out.append(Finding(note.rel, ERROR, "missing-required-field",
                               f"required field `{fld}` is missing or empty"))

    for fld, allowed in schema.enums.items():
        val = note.fm.get(fld)
        if not is_empty(val) and str(val) not in allowed:
            out.append(Finding(note.rel, ERROR, "bad-enum-value",
                               f"`{fld}: {val}` — allowed: {sorted(allowed)}"))

    for fld, allowed in schema.list_enums.items():
        val = note.fm.get(fld)
        if isinstance(val, list):
            bad = [v for v in val if str(v) not in allowed]
            if bad:
                out.append(Finding(note.rel, ERROR, "bad-enum-value",
                                   f"`{fld}` has {bad} — allowed: {sorted(allowed)}"))

    for fld in schema.full_dates:
        val = note.fm.get(fld)
        if not is_empty(val) and not FULL_DATE_RE.match(str(val)):
            out.append(Finding(note.rel, ERROR, "bad-date-format",
                               f"`{fld}: {val}` is not YYYY-MM-DD"))
    for fld in schema.year_dates:
        val = note.fm.get(fld)
        if not is_empty(val) and not YEAR_DATE_RE.match(str(val)):
            out.append(Finding(note.rel, ERROR, "bad-date-format",
                               f"`{fld}: {val}` is not YYYY[-MM[-DD]]"))

    return out


def check_sections(note: Note) -> list[Finding]:
    schema = SCHEMAS.get(note.type)
    if schema is None:
        return []
    required = list(schema.sections)
    if note.type == "moc" and note.fm.get("kind") == "thread":
        required = ["Current state", "Timeline"]
    present = {s.lower() for s in note.sections()}
    return [Finding(note.rel, WARNING, "missing-section",
                    f"expected a `## {s}` section")
            for s in required if s.lower() not in present]


def check_field_types(note: Note) -> list[Finding]:
    schema = SCHEMAS.get(note.type)
    if schema is None:
        return []
    out: list[Finding] = []
    for fld in schema.list_fields:
        val = note.fm.get(fld)
        if is_empty(val) or isinstance(val, list):
            continue
        out.append(Finding(note.rel, ERROR, "bad-field-type",
                           f"`{fld}: {val}` should be a YAML list, e.g. `{fld}: [{val}]`"))
    return out


def check_sectors(note: Note) -> list[Finding]:
    if note.type != "company":
        return []
    sectors = note.fm.get("sectors")
    if not isinstance(sectors, list):
        return []
    return [Finding(note.rel, WARNING, "unknown-sector",
                    f"sector `{s}` not in taxonomy (typo? or add it to meta/taxonomy.md)")
            for s in sectors if str(s) not in KNOWN_SECTORS]


def check_links(note: Note, index: dict[str, Note]) -> list[Finding]:
    out: list[Finding] = []
    for target, line in wikilink_targets(note.body):
        key = resolve_key(target)
        if key in index:
            continue
        is_source = target.lower().startswith("sources/")
        if is_source:
            out.append(Finding(note.rel, ERROR, "broken-source-link",
                               f"citation `[[{target}]]` resolves to no source note", line))
        else:
            out.append(Finding(note.rel, WARNING, "unresolved-link",
                               f"`[[{target}]]` — a marker for a future note, or a typo",
                               line))
    return out


def check_timeline_citations(note: Note) -> list[Finding]:
    if note.type not in {"company", "person", "technology", "moc"}:
        return []
    if note.is_seed:
        return []
    timeline = section_body(note.body, "Timeline")
    out: list[Finding] = []
    for i, line in enumerate(timeline.splitlines()):
        if DATED_BULLET_RE.match(line) and "[[sources/" not in line:
            out.append(Finding(note.rel, ERROR, "uncited-timeline-bullet",
                               f"dated entry has no [[sources/...]] citation: {line.strip()[:70]}"))
    return out


def check_volatile_support(note: Note) -> list[Finding]:
    if note.type != "company" or note.is_seed:
        return []
    populated = [f for f in VOLATILE_COMPANY_FIELDS if not is_empty(note.fm.get(f))]
    if not populated:
        return []
    timeline = section_body(note.body, "Timeline")
    if "[[sources/" in timeline:
        return []
    return [Finding(note.rel, WARNING, "unsupported-volatile-field",
                    f"{populated} set but no cited `## Timeline` entry to support them")]


def check_source_archive(note: Note) -> list[Finding]:
    if note.type != "source":
        return []
    if is_empty(note.fm.get("archive_url")):
        return [Finding(note.rel, WARNING, "missing-archive",
                        "no `archive_url` — provenance is not durable until archived")]
    return []


def check_stub(note: Note) -> list[Finding]:
    if note.type not in SCHEMAS:
        return []
    if prose_length(note.body) < 120:
        return [Finding(note.rel, WARNING, "stub", "note has almost no prose content")]
    return []


def check_stale_watchlist(note: Note, today: dt.date) -> list[Finding]:
    if note.type != "company" or not note.fm.get("watchlist"):
        return []
    updated = note.fm.get("updated")
    if is_empty(updated) or not FULL_DATE_RE.match(str(updated)):
        return []
    age = (today - dt.date.fromisoformat(str(updated))).days
    if age > 90:
        return [Finding(note.rel, WARNING, "stale-watchlist",
                        f"watchlist company not updated in {age} days")]
    return []


def check_duplicate_names(by_key: dict[str, list[Note]]) -> list[Finding]:
    out: list[Finding] = []
    for key, notes in by_key.items():
        if len(notes) < 2:
            continue
        paths = sorted(n.rel for n in notes)
        for n in notes:
            if top_dir(n.rel) not in LINT_DIRS or n.type not in SCHEMAS:
                continue
            others = [p for p in paths if p != n.rel]
            out.append(Finding(n.rel, ERROR, "duplicate-name",
                               f"name/alias `{key}` also resolves to {others} — "
                               f"[[{key}]] links will silently pick one"))
    return out


def check_orphans(notes: list[Note], index: dict[str, Note]) -> list[Finding]:
    inbound: dict[str, int] = {n.rel: 0 for n in notes}
    for n in notes:
        seen: set[str] = set()
        for target, _ in wikilink_targets(n.body):
            key = resolve_key(target)
            tgt = index.get(key)
            if tgt and tgt.rel != n.rel and tgt.rel not in seen:
                seen.add(tgt.rel)
                inbound[tgt.rel] = inbound.get(tgt.rel, 0) + 1
    out: list[Finding] = []
    for n in notes:
        if inbound.get(n.rel, 0) > 0:
            continue
        if n.type in {"concept", "meta", "dashboard"} or n.is_seed:
            continue
        if n.type not in SCHEMAS:
            continue
        out.append(Finding(n.rel, WARNING, "orphan",
                           "no inbound links — add one only if a real relationship exists"))
    return out


# --------------------------------------------------------------------------- driver

def lint_vault(root: Path, only: list[Path] | None = None,
               today: dt.date | None = None) -> list[Finding]:
    root = root.resolve()
    today = today or dt.date.today()

    all_notes = [load_note(p, root) for p in iter_markdown(root)]

    by_key: dict[str, list[Note]] = {}
    for n in all_notes:
        for key in n.names():
            by_key.setdefault(key, []).append(n)
    index: dict[str, Note] = {key: notes[0] for key, notes in by_key.items()}

    linted = [n for n in all_notes if top_dir(n.rel) in LINT_DIRS]

    findings: list[Finding] = check_duplicate_names(by_key)
    for n in linted:
        fm = check_frontmatter(n)
        findings += fm
        if any(f.rule == "frontmatter-invalid" for f in fm):
            continue
        findings += check_schema(n)
        findings += check_field_types(n)
        findings += check_sections(n)
        findings += check_sectors(n)
        findings += check_links(n, index)
        findings += check_timeline_citations(n)
        findings += check_volatile_support(n)
        findings += check_source_archive(n)
        findings += check_stub(n)
        findings += check_stale_watchlist(n, today)

    findings += check_orphans(linted, index)

    if only is not None:
        wanted = {str(p.resolve().relative_to(root)) for p in only}
        findings = [f for f in findings if f.path in wanted]

    return sorted(findings, key=lambda f: (f.severity != ERROR, f.path, f.rule))


def render_report(findings: list[Finding], today: dt.date) -> str:
    errors = [f for f in findings if f.severity == ERROR]
    warnings = [f for f in findings if f.severity == WARNING]
    lines = [
        "---", "type: meta", "name: Lint report", f"updated: {today.isoformat()}", "---",
        "", "# Lint report", "",
        f"_Generated by `tools/lint.py` on {today.isoformat()}._", "",
        f"- **Errors:** {len(errors)}", f"- **Warnings:** {len(warnings)}", "",
    ]
    for label, group in (("Errors", errors), ("Warnings", warnings)):
        lines.append(f"## {label}")
        lines.append("")
        if not group:
            lines.append("_None._")
        else:
            for f in group:
                loc = f"{f.path}:{f.line}" if f.line else f.path
                lines.append(f"- `{f.rule}` — {loc} — {f.message}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge-base vault.")
    parser.add_argument("paths", nargs="*", type=Path,
                        help="specific files to report on (index still built from all)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--strict", action="store_true",
                        help="warnings also cause a non-zero exit")
    parser.add_argument("--no-report", action="store_true",
                        help="do not write meta/health/lint-report.md")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    today = dt.date.today()
    findings = lint_vault(root, only=args.paths or None, today=today)

    errors = [f for f in findings if f.severity == ERROR]
    warnings = [f for f in findings if f.severity == WARNING]

    for f in findings:
        print(f.format())
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    if not args.no_report and not args.paths:
        report_path = root / "meta" / "health" / "lint-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_report(findings, today), encoding="utf-8")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
