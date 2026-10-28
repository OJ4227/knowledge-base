#!/usr/bin/env python3
"""Entity resolution for Enrich (Stage 3): pure logic, no API calls.

For every entity string in a Triage item, decides whether it matches an existing vault
note, clears the "≥2 independent mentions" bar (`meta/agent-instructions/enrich.md`, hard
rule 5) via a prior mention, or is a genuine first mention. Reuses `tools/lint.py`'s note
loading and wikilink helpers rather than reimplementing vault indexing — see
`meta/agent-instructions/enrich.md` for the rules this implements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import lint

PENDING_ENTITIES_PATH = Path(__file__).resolve().parent.parent / "meta" / "pending-entities.md"

_ENTITY_HEADING_RE = re.compile(r"^###\s+(.+)$", re.M)
_TIMELINE_BULLET_RE = re.compile(r"^-\s+\d{4}-\d{2}-\d{2}\s+[—-]\s+.+$", re.M)


# --------------------------------------------------------------------------- vault index

@dataclass
class VaultIndex:
    by_name: dict[str, lint.Note]                 # resolve_key(name) -> Note
    unresolved_link_targets: set[str]              # resolve_key(target) for dangling [[links]]


def build_vault_index(root: Path) -> VaultIndex:
    notes = [lint.load_note(p, root) for p in lint.iter_markdown(root)]

    by_name: dict[str, lint.Note] = {}
    for n in notes:
        for key in n.names():
            by_name.setdefault(key, n)

    unresolved: set[str] = set()
    for n in notes:
        for target, _line in lint.wikilink_targets(n.body):
            key = lint.resolve_key(target)
            if key not in by_name:
                unresolved.add(key)

    return VaultIndex(by_name=by_name, unresolved_link_targets=unresolved)


# --------------------------------------------------------------------------- pending facts

@dataclass
class PendingFact:
    text: str              # the exact timeline-bullet line, e.g. "- 2025-03-12 — ... #routine"


@dataclass
class PendingStore:
    facts: dict[str, list[PendingFact]] = field(default_factory=dict)  # entity name -> facts

    def has_entity(self, name: str) -> bool:
        return name in self.facts and len(self.facts[name]) > 0


def load_pending_store(path: Path = PENDING_ENTITIES_PATH) -> PendingStore:
    if not path.exists():
        return PendingStore()
    text = path.read_text(encoding="utf-8")
    _fm, body = lint.split_frontmatter(text)
    body = body or text

    facts: dict[str, list[PendingFact]] = {}
    headings = list(_ENTITY_HEADING_RE.finditer(body))
    for i, m in enumerate(headings):
        name = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        section = body[start:end]
        bullets = [line.strip() for line in section.splitlines()
                   if _TIMELINE_BULLET_RE.match(line.strip())]
        if bullets:
            facts[name] = [PendingFact(text=b) for b in bullets]
    return PendingStore(facts=facts)


def render_pending_store(store: PendingStore) -> str:
    header = """---
type: meta
name: Pending entities
updated: {date}
---

# Pending entities

Entities mentioned in Triage output that haven't yet cleared the "≥2 independent
mentions" bar (`meta/agent-instructions/enrich.md`, hard rule 5) for a new tracked note.
Rule 5 exists to avoid note *bloat*, not to discard information — every entry below is a
full, cited, timeline-ready fact in exactly the format defined in `meta/schema.md`'s
"Timeline entry format," not a stripped "mentioned once" marker. When a second mention
arrives, Enrich creates the note and moves every stored fact in verbatim as real
`## Timeline` entries.

An existing unresolved `[[EntityName]]` link anywhere in the vault also counts as a prior
mention — an entity can clear the bar via a link already written by hand, even with zero
entries here.

Enrich reads and updates this file every run. Format: one `### EntityName` heading per
pending entity, followed by its stored facts as ordinary timeline bullets (oldest first).

## Entries

"""
    import datetime as dt
    out = header.format(date=dt.date.today().isoformat())
    if not store.facts:
        return out + "_(none yet)_\n"
    for name in sorted(store.facts):
        out += f"### {name}\n\n"
        for fact in store.facts[name]:
            out += f"{fact.text}\n"
        out += "\n"
    return out.rstrip() + "\n"


def save_pending_store(store: PendingStore, path: Path = PENDING_ENTITIES_PATH) -> None:
    path.write_text(render_pending_store(store), encoding="utf-8")


# --------------------------------------------------------------------------- resolution

@dataclass
class Resolution:
    kind: str                              # "matched" | "pending_second_mention" | "pending_first_mention"
    note: lint.Note | None = None          # set when kind == "matched"
    prior_facts: list[PendingFact] = field(default_factory=list)  # set when second mention


def resolve_entity(name: str, index: VaultIndex, pending: PendingStore) -> Resolution:
    key = lint.resolve_key(name)

    note = index.by_name.get(key)
    if note is not None:
        return Resolution(kind="matched", note=note)

    has_unresolved_link = key in index.unresolved_link_targets
    has_pending_fact = pending.has_entity(name)

    if has_unresolved_link or has_pending_fact:
        return Resolution(kind="pending_second_mention",
                          prior_facts=list(pending.facts.get(name, [])))

    return Resolution(kind="pending_first_mention")
