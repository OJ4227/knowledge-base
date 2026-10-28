---
type: meta
name: Pending entities
updated: 2026-10-28
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

_(none yet)_
