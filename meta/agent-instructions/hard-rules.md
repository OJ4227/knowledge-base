---
type: meta
name: Hard rules
updated: 2026-10-28
---

# Hard rules — never break these

Shared across every pipeline stage. Read `DESIGN.md` for the full rationale. These govern
the pipeline agents and routine maintenance sessions — **not** owner-directed
build/scaffolding work. `CLAUDE.md` points here when a session is operating the pipeline
or maintaining vault content.

1. **Timelines are append-only.** Never rewrite or delete a `## Timeline` entry. Corrections
   are new dated entries. Old `#routine` entries are *moved* (by the gardener) to
   `companies/_timeline/<slug>-archive.md` with a pointer left behind — never deleted.
2. **Cite every fact.** No `## Timeline` bullet and no frontmatter value in a tracked note
   without at least one `[[sources/...]]` reference. Every frontmatter fact must trace to a
   cited timeline entry.
3. **Curated prose is owner-only.** Never edit a `<!-- curated -->` block. The sole
   exception: the one designated `## State of the art` (technology) / `## Current state`
   (thread) block per note, which the gardener maintains. Concept note bodies are never
   edited in place — draft and propose only.
4. **Additive auto, destructive proposed.** Adding links, aliases, MOC membership,
   `related:` entries, and cited timeline bullets: apply directly, log in the weekly digest.
   Merges, deletions, content removal, section restructuring: write a proposal to
   `meta/review/YYYY-WW.md`, do not apply.
5. **New tracked notes only when earned.** Create a `company` / `technology` / `person` /
   `thread` note only when the entity has ≥2 independent mentions or the owner flagged it.
   Otherwise leave the capture in the thread/entity it relates to.
6. **Never auto-create concept notes.** Flag gaps in `meta/health/report.md`.
7. **Deterministic work is code, not you.** Link checking, schema validation, RSS parsing,
   structured-data ingestion run as scripts. Use an LLM step only for judgment.
8. **One atomic commit per logical change**, with a message saying what and why, e.g.
   `enrich: Figure AI — $675M Series C timeline entry (src: the-batch 2024-02-29)`.
9. **Idempotent.** A re-run with no new input produces no changes. Respect
   `meta/rejected-links.md`.
