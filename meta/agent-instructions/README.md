---
type: meta
name: Agent instructions
updated: 2026-10-28
---

# Agent instructions

Operating rules for the automated pipeline, split one file per stage so each pipeline
script can load exactly its own rules at runtime (`tools/triage.py`, `tools/enrich.py`,
...) without fragile heading-text slicing out of a single large file. These govern the
pipeline agents and routine maintenance sessions — **not** owner-directed build/scaffolding
work. `CLAUDE.md` points here when a session is operating the pipeline or maintaining
vault content.

Read `DESIGN.md` for the full rationale.

- [Hard rules](hard-rules.md) — shared across every stage, read this first
- [Collectors](collectors.md) — Stage 1
- [Triage](triage.md) — Stage 2
- [Enrich](enrich.md) — Stage 3
- [Daily digest](daily-digest.md) — Stage 4
- [Gardener](gardener.md) — Stage 5
- [Weekly digest](weekly-digest.md) — Stage 6
- [Lint](lint.md) — `tools/lint.py` checks reference
