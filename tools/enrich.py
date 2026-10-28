#!/usr/bin/env python3
"""Stage 3 pipeline step: Enrich.

Reads a Triage output file (`inbox/_triage/YYYY-MM-DD.json`), resolves each item's
entities against the vault (`tools/enrich_resolve.py`), and asks the model to propose
structured actions: timeline entries on existing notes, frontmatter rollups, new notes for
entities that clear the "≥2 mentions" bar, concept links, opinion-to-thread links, and
explicit skips. A Python layer enforces the rules that must never be violated (every
timeline entry cited, no opinion item gets a timeline entry, no name collision, nothing in
`meta/rejected-links.md`) and performs the actual file edits — the model never writes a
full file verbatim. See `DESIGN.md` §7 and `meta/agent-instructions/enrich.md` for how this
fits the pipeline.

Usage:
    python tools/enrich.py --input inbox/_triage/2026-10-27.json              # preview, no writes
    python tools/enrich.py --input inbox/_triage/2026-10-27.json --apply      # real writes
    python tools/enrich.py --input inbox/_triage/2026-10-27.json --dry-run    # print prompt, no API call

Requires one of, in the environment (source tools/.env first):
  - ANTHROPIC_API_KEY                         — direct Anthropic API
  - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN — a gateway/proxy in front of the API
    (e.g. a corporate relay) that speaks Bearer auth instead of an Anthropic key
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

import enrich_resolve as er
import lint
import triage as tg  # reuse build_client(), DEFAULT_MODEL, DEFAULT_EFFORT

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "tools" / "prompts" / "enrich.md"
ENRICH_RULES_PATH = ROOT / "meta" / "agent-instructions" / "enrich.md"
HARD_RULES_PATH = ROOT / "meta" / "agent-instructions" / "hard-rules.md"
SCHEMA_PATH = ROOT / "meta" / "schema.md"
REJECTED_LINKS_PATH = ROOT / "meta" / "rejected-links.md"
TEMPLATES_DIR = ROOT / "templates"

ACTION_TYPES = ("timeline_entry", "frontmatter_patch", "new_note", "concept_link",
                "key_link", "skip")
NOTE_TYPES = ("company", "person", "technology", "moc")
VOLATILE_FIELDS = ("total_funding_usd", "last_round", "stage", "status")
TYPE_DIR = {"company": "companies", "person": "people", "technology": "technologies",
            "moc": "topics"}


# --------------------------------------------------------------------------- schema

class TimelineEntrySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    text: str
    tag: Literal["milestone", "routine"]
    claim_tag: Literal["claim/reported", "claim/rumored", "claim/disputed"] | None = None
    sources: list[str]


class EnrichAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal[ACTION_TYPES]
    item_id: str
    target_note: str | None = None
    timeline_entry: TimelineEntrySpec | None = None
    frontmatter_field: Literal[VOLATILE_FIELDS] | None = None
    frontmatter_value: str | None = None
    new_note_type: Literal[NOTE_TYPES] | None = None
    new_note_path: str | None = None
    new_note_frontmatter_yaml: str | None = None
    new_note_timeline_entries: list[TimelineEntrySpec] | None = None
    concept: str | None = None
    target_thread: str | None = None
    key_link_text: str | None = None
    key_link_source: str | None = None
    reason: str | None = None


class EnrichResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[EnrichAction]


# --------------------------------------------------------------------------- loading triage output

@dataclass
class TriageItemView:
    id: str
    title: str
    summary: str
    domains: list[str]
    development_type: str
    entities: list[str]
    concepts: list[str]
    sources: list[str]
    claim_status: str
    reason: str | None


def load_triage_items(path: Path) -> list[TriageItemView]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [TriageItemView(**item) for item in data["items"]]


# --------------------------------------------------------------------------- rejected links

def load_rejected_pairs(path: Path = REJECTED_LINKS_PATH) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    pairs = set()
    for m in re.finditer(r"\[\[([^\]]+)\]\]\s*↔\s*\[\[([^\]]+)\]\]", text):
        a, b = lint.resolve_key(m.group(1)), lint.resolve_key(m.group(2))
        pairs.add((a, b))
        pairs.add((b, a))
    return pairs


# --------------------------------------------------------------------------- prompt assembly

def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL).strip()


def load_enrich_rules() -> str:
    return strip_frontmatter(ENRICH_RULES_PATH.read_text(encoding="utf-8"))


def load_hard_rules() -> str:
    return strip_frontmatter(HARD_RULES_PATH.read_text(encoding="utf-8"))


def load_schema_excerpts() -> str:
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    start = text.index("## `company`")
    end = text.index("## `source`")
    company_through_moc = text[start:end].strip()
    timeline_start = text.index("## Timeline entry format")
    timeline_format = text[timeline_start:].strip()
    return company_through_moc + "\n\n" + timeline_format


def render_resolution(name: str, resolution: er.Resolution) -> str:
    if resolution.kind == "matched":
        return f"  - {name!r} -> matched: {resolution.note.rel}"
    if resolution.kind == "pending_second_mention":
        facts = "; ".join(f.text for f in resolution.prior_facts) or "(via existing unresolved link)"
        return f"  - {name!r} -> pending (second mention, eligible for a new note now): {facts}"
    return f"  - {name!r} -> pending (first mention, not yet eligible)"


def render_items_block(items: list[TriageItemView], index: er.VaultIndex,
                        pending: er.PendingStore) -> str:
    parts = []
    for item in items:
        resolutions = "\n".join(
            render_resolution(e, er.resolve_entity(e, index, pending)) for e in item.entities
        )
        parts.append(
            f"### {item.id}\n"
            f"- title: {item.title}\n"
            f"- summary: {item.summary}\n"
            f"- domains: {item.domains}\n"
            f"- development_type: {item.development_type}\n"
            f"- concepts: {item.concepts}\n"
            f"- sources: {item.sources}\n"
            f"- claim_status: {item.claim_status}\n"
            f"- reason: {item.reason}\n"
            f"- entity resolutions:\n{resolutions}\n"
        )
    return "\n".join(parts)


def build_prompt(items: list[TriageItemView], index: er.VaultIndex,
                  pending: er.PendingStore) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        enrich_rules=load_enrich_rules(),
        hard_rules=load_hard_rules(),
        schema_excerpts=load_schema_excerpts(),
        items=render_items_block(items, index, pending),
    )


# --------------------------------------------------------------------------- hard guards

@dataclass
class Rejection:
    action: EnrichAction
    reason: str


def format_timeline_line(t: TimelineEntrySpec) -> str:
    tags = f"#{t.tag}"
    if t.claim_tag:
        tags += f" #{t.claim_tag}"
    sources = " ".join(t.sources)
    return f"- {t.date} — {t.text} ({sources}) {tags}"


def validate_actions(actions: list[EnrichAction], index: er.VaultIndex,
                      rejected_pairs: set[tuple[str, str]],
                      opinion_item_ids: set[str]) -> tuple[list[EnrichAction], list[Rejection]]:
    """Defense in depth: enforce the rules that must never be violated, regardless of what
    the model proposed. Returns (accepted, rejected)."""
    accepted: list[EnrichAction] = []
    rejected: list[Rejection] = []

    for a in actions:
        if a.action_type == "skip":
            accepted.append(a)
            continue

        if a.action_type == "timeline_entry":
            if a.item_id in opinion_item_ids:
                rejected.append(Rejection(a, "opinion items never get a timeline_entry "
                                             "(DESIGN.md §2 — opinion is a ledger exception)"))
                continue
            if a.target_note is None or lint.resolve_key(a.target_note) not in index.by_name:
                rejected.append(Rejection(a, f"target_note {a.target_note!r} not found in vault index"))
                continue
            if not a.timeline_entry or not a.timeline_entry.sources:
                rejected.append(Rejection(a, "timeline_entry with zero sources (hard rule 2)"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "frontmatter_patch":
            if a.target_note is None or lint.resolve_key(a.target_note) not in index.by_name:
                rejected.append(Rejection(a, f"target_note {a.target_note!r} not found in vault index"))
                continue
            if a.frontmatter_field is None or a.frontmatter_value is None:
                rejected.append(Rejection(a, "frontmatter_patch missing field/value"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "new_note":
            if not a.new_note_path or not a.new_note_type:
                rejected.append(Rejection(a, "new_note missing path/type"))
                continue
            if a.item_id in opinion_item_ids:
                rejected.append(Rejection(a, "opinion items never produce timeline entries, "
                                             "including inside a new_note (DESIGN.md §2)"))
                continue
            stem = Path(a.new_note_path).stem
            if lint.resolve_key(stem) in index.by_name:
                rejected.append(Rejection(a, f"name/alias collision: {stem!r} already resolves "
                                             f"to {index.by_name[lint.resolve_key(stem)].rel}"))
                continue
            if not a.new_note_timeline_entries:
                rejected.append(Rejection(a, "new_note with no timeline entries"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "concept_link":
            if lint.resolve_key(a.concept or "") not in index.by_name:
                rejected.append(Rejection(a, f"concept {a.concept!r} has no existing concept "
                                             f"note — never auto-create one (hard rule 6)"))
                continue
            pair = (lint.resolve_key(a.target_note or ""), lint.resolve_key(a.concept or ""))
            if pair in rejected_pairs:
                rejected.append(Rejection(a, "link rejected previously — see meta/rejected-links.md"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "key_link":
            if a.target_thread is None or lint.resolve_key(a.target_thread) not in index.by_name:
                rejected.append(Rejection(a, f"target_thread {a.target_thread!r} not found in vault index"))
                continue
            accepted.append(a)
            continue

    return accepted, rejected


# --------------------------------------------------------------------------- applying actions

def insert_timeline_bullet(body: str, line: str, date: str) -> str:
    """Insert `line` under the `### YYYY` heading matching `date`'s year, newest-first.
    Creates the year heading (in the right position) if it doesn't exist yet."""
    year = date[:4]
    heading = f"### {year}"
    timeline_idx = body.index("## Timeline")
    section_end = len(body)
    next_heading = re.search(r"\n## ", body[timeline_idx + 1:])
    if next_heading:
        section_end = timeline_idx + 1 + next_heading.start()
    section = body[timeline_idx:section_end]

    if heading in section:
        h_idx = section.index(heading) + len(heading)
        rest = section[h_idx:]
        next_h = re.search(r"\n### ", rest[1:])
        insert_at = h_idx + (1 + next_h.start() if next_h else len(rest))
        new_section = section[:h_idx] + "\n" + line + section[h_idx:insert_at] + section[insert_at:]
    else:
        # insert the new year heading in descending order among existing ### headings
        year_headings = [(m.group(1), m.start()) for m in re.finditer(r"### (\d{4})", section)]
        insert_pos = len(section)
        for y, pos in year_headings:
            if year > y:
                insert_pos = pos
                break
        new_section = section[:insert_pos] + f"{heading}\n{line}\n\n" + section[insert_pos:]

    return body[:timeline_idx] + new_section + body[section_end:]


def apply_frontmatter_patch(path: Path, field_name: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm_text) or {}
    data[field_name] = value
    data["updated"] = dt.date.today().isoformat()
    new_fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")


def apply_timeline_entry(path: Path, entry: TimelineEntrySpec) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm_text) or {}
    data["updated"] = dt.date.today().isoformat()
    new_fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()

    line = format_timeline_line(entry)
    new_body = insert_timeline_bullet(body, line, entry.date)
    path.write_text(f"---\n{new_fm}\n---\n{new_body}", encoding="utf-8")


def apply_concept_link(path: Path, concept_target: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    link = f"[[{concept_target}]]"
    if link in body:
        return
    dev_idx = body.find("## Developments")
    if dev_idx != -1:
        insert_at = body.index("\n", dev_idx) + 1
        body = body[:insert_at] + f"\n- {link}\n" + body[insert_at:]
    else:
        body = body.rstrip() + f"\n\n## Related concepts\n\n- {link}\n"
    path.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def apply_key_link(path: Path, text_line: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    kl_idx = body.rfind("## Key links")
    entry = f"- {text_line} ({source})"
    insert_at = body.index("\n", kl_idx) + 1 if kl_idx != -1 else len(body)
    body = body[:insert_at] + f"{entry}\n" + body[insert_at:]
    path.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def create_new_note(action: EnrichAction) -> Path:
    template_path = TEMPLATES_DIR / f"{action.new_note_type}.md"
    template_text = template_path.read_text(encoding="utf-8")
    _tmpl_fm, tmpl_body = lint.split_frontmatter(template_text)

    patch = yaml.safe_load(action.new_note_frontmatter_yaml or "{}") or {}
    today = dt.date.today().isoformat()
    patch.setdefault("created", today)
    patch["updated"] = today

    new_fm = yaml.safe_dump(patch, sort_keys=False, allow_unicode=True).strip()

    body = tmpl_body
    for entry in action.new_note_timeline_entries or []:
        line = format_timeline_line(entry)
        body = insert_timeline_bullet(body, line, entry.date)

    out_path = ROOT / action.new_note_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- preview / apply

def describe_action(a: EnrichAction) -> str:
    if a.action_type == "timeline_entry":
        return (f"[timeline_entry] {a.target_note}: "
                f"{format_timeline_line(a.timeline_entry)}")
    if a.action_type == "frontmatter_patch":
        return f"[frontmatter_patch] {a.target_note}: {a.frontmatter_field} = {a.frontmatter_value}"
    if a.action_type == "new_note":
        lines = "\n".join(f"    {format_timeline_line(t)}"
                          for t in a.new_note_timeline_entries or [])
        return f"[new_note] {a.new_note_path} ({a.new_note_type})\n{lines}"
    if a.action_type == "concept_link":
        return f"[concept_link] {a.target_note}: [[{a.concept}]]"
    if a.action_type == "key_link":
        return f"[key_link] {a.target_thread}: {a.key_link_text} ({a.key_link_source})"
    return f"[skip] {a.item_id}: {a.reason}"


def apply_action(a: EnrichAction) -> None:
    if a.action_type == "timeline_entry":
        apply_timeline_entry(ROOT / a.target_note, a.timeline_entry)
    elif a.action_type == "frontmatter_patch":
        apply_frontmatter_patch(ROOT / a.target_note, a.frontmatter_field, a.frontmatter_value)
    elif a.action_type == "new_note":
        create_new_note(a)
    elif a.action_type == "concept_link":
        apply_concept_link(ROOT / a.target_note, a.concept)
    elif a.action_type == "key_link":
        apply_key_link(ROOT / a.target_thread, a.key_link_text, a.key_link_source)
    # skip: nothing to apply


def touched_paths(actions: list[EnrichAction]) -> list[Path]:
    paths = []
    for a in actions:
        if a.action_type in ("timeline_entry", "frontmatter_patch", "concept_link"):
            paths.append(ROOT / a.target_note)
        elif a.action_type == "key_link":
            paths.append(ROOT / a.target_thread)
        elif a.action_type == "new_note":
            paths.append(ROOT / a.new_note_path)
    return list(dict.fromkeys(paths))  # de-dup, preserve order


# --------------------------------------------------------------------------- main

def run(input_path: Path, apply: bool, dry_run: bool, model: str, effort: str) -> int:
    items = load_triage_items(input_path)
    index = er.build_vault_index(ROOT)
    pending = er.load_pending_store()

    prompt = build_prompt(items, index, pending)
    print(f"assembled prompt for {len(items)} item(s), model={model}, effort={effort}")

    if dry_run:
        print("\n--- dry run: prompt below, no API call made ---\n")
        print(prompt)
        return 0

    client = tg.build_client()
    if client is None:
        print("No credentials found. Set ANTHROPIC_API_KEY, or ANTHROPIC_BASE_URL + "
              "ANTHROPIC_AUTH_TOKEN for a gateway. Source tools/.env first.",
              file=sys.stderr)
        return 1

    with client.messages.stream(
        model=model,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": prompt,
                         "cache_control": {"type": "ephemeral"}}],
        }],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": EnrichResult.model_json_schema()},
        },
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    result = EnrichResult.model_validate_json(text)

    rejected_pairs = load_rejected_pairs()
    opinion_item_ids = {item.id for item in items if item.development_type == "opinion"}
    accepted, rejected = validate_actions(result.actions, index, rejected_pairs, opinion_item_ids)

    print(f"\n{len(accepted)} action(s) accepted, {len(rejected)} rejected by hard guards:\n")
    for a in accepted:
        print(f"  {describe_action(a)}")
    for r in rejected:
        print(f"  [REJECTED] {describe_action(r.action)} — {r.reason}")

    if not apply:
        print(f"\npreview only — no files written. Re-run with --apply to write "
              f"{len(accepted)} accepted action(s).")
        return 0

    for a in accepted:
        apply_action(a)

    paths = touched_paths(accepted)
    print(f"\napplied {len(accepted)} action(s) across {len(paths)} file(s)")

    lint_findings = lint.lint_vault(ROOT, only=paths)
    errors = [f for f in lint_findings if f.severity == lint.ERROR]
    if errors:
        print(f"\nLINT FAILED after apply — {len(errors)} error(s) on touched files:",
              file=sys.stderr)
        for f in errors:
            print(f.format(), file=sys.stderr)
        return 1

    print("lint: 0 errors on touched files")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="path to a Triage output JSON file")
    parser.add_argument("--apply", action="store_true",
                        help="write the accepted actions to disk (default: preview only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the assembled prompt, make no API call")
    parser.add_argument("--model", default=tg.DEFAULT_MODEL)
    parser.add_argument("--effort", default=tg.DEFAULT_EFFORT,
                        choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args(argv)
    return run(input_path=args.input, apply=args.apply, dry_run=args.dry_run,
               model=args.model, effort=args.effort)


if __name__ == "__main__":
    raise SystemExit(main())
