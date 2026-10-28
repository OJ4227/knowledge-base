---
type: meta
name: Enrich instructions
updated: 2026-10-28
---

# Enrich (Stage 3, daily, one LLM context)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.
Loaded at runtime by `tools/enrich.py` and interpolated into `tools/prompts/enrich.md` —
this file is the single source of truth for Enrich's rules, never restated in the prompt
itself.

- Route each classified item to the relevant `company` / `technology` / `topic` note(s),
  and add `[[concepts/...]]` links where a concept is touched.
- An `opinion` item never gets a `## Timeline` entry — it has no event to ledger. Route a
  kept opinion piece to the relevant thread's `## Key links` instead.
- Append a `## Timeline` entry per the format in `meta/schema.md`, tagged `#milestone` or
  `#routine`, with source citation(s), for every non-opinion item.
- Update frontmatter rollups (`total_funding_usd`, `last_round`, `stage`, `status`,
  `updated`) — only where a new cited timeline entry supports it.
- Create new tracked notes only under hard rule 5, from `templates/`. Rule 5's "≥2
  independent mentions" bar counts an existing unresolved `[[EntityName]]` link anywhere in
  the vault as a prior mention, alongside a prior Enrich-recorded mention in
  `meta/pending-entities.md`.
- An entity that doesn't clear the ≥2-mentions bar is never silently dropped: its full
  cited fact is stored in `meta/pending-entities.md` (exact text, citation, tag) until a
  second mention arrives, at which point the note is created and every stored fact is moved
  in verbatim as real timeline entries. Rule 5 exists to avoid note *bloat*, not to
  discard information — see `DESIGN.md` §2.
- Never touch curated blocks. Never edit concept bodies.
