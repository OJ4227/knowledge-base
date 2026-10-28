---
type: meta
name: Triage instructions
updated: 2026-10-28
---

# Triage (Stage 2, daily, one LLM context)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.
Loaded at runtime by `tools/triage.py` (`load_triage_rules()`) and interpolated into
`tools/prompts/triage.md` — this file is the single source of truth for Triage's rules,
never restated in the prompt itself.

- Read all `inbox/` raw captures.
- **Fan out, don't stay 1:1.** A single newsletter file commonly bundles several
  independent developments — emit one classified item per development, not one per input
  file.
- Deduplicate across all streams in this single context (same event from 3 newsletters = 1
  item with 3 source links).
- Classify each item on both taxonomy axes (`meta/taxonomy.md`).
- Drop noise (pure marketing, signup/onboarding chrome, already-known facts). **Opinion is
  not automatically noise** — classify it `opinion` and apply the keep bar in
  `meta/taxonomy.md`: keep only if it makes a non-obvious claim, judged on the body, never
  the headline. Record a one-line `reason` on every `opinion` item and every dropped item.
- Flag recurring unfamiliar terms as concept-note gaps.
- Emit one classified-items file for the run; remove processed raw captures from `inbox/`.
