---
type: meta
name: Daily digest instructions
updated: 2026-10-28
---

# Daily digest (Stage 4, daily, after Enrich)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.

- Summarize only today's Enrich output — not a rollup, a same-day read.
- `## Watchlist alerts` first: every `watchlist: true` company that got a new `## Timeline`
  entry today, `#milestone` and `#routine` alike (link to the entry, one line each).
- `## Opinion & analysis` next: today's kept `opinion` items, with their recorded `reason`
  — this is the only place a kept opinion piece surfaces same-day.
- Then the same category breakdown as the weekly digest (technical / threads / business /
  new entities / concept gaps), scoped to today only.
- Write `digests/YYYY-MM-DD.md`. No new notification channel — this file is the alert.
