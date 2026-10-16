---
type: meta
name: Digests
updated: 2026-08-30
---

# digests/

Two cadences, both written here:

- **Daily** — `YYYY-MM-DD.md`, written by the Daily digest agent (`DESIGN.md` §7 Stage 4)
  right after Enrich runs. A short same-day read, led by `## Watchlist alerts` — every
  `watchlist: true` company (`meta/schema.md`) that got a new `## Timeline` entry that day.
  This is also the watchlist alert mechanism: no separate notification channel exists.
- **Weekly** — `YYYY-WW.md` (ISO week), written by the Weekly digest agent (Stage 6). The
  deeper rollup, read alongside `git log` to see everything the pipeline did that week.

Daily sections:

```
## Watchlist alerts
## Technical developments   (AI / Robotics / Compute-hardware)
## Threads that moved
## Business                 (Funding / People / M&A / Shutdowns)
## New entities added today
## Concept gaps flagged
```

Weekly sections:

```
## Technical developments   (AI / Robotics / Compute-hardware)
## Threads that moved
## Business                 (Funding / People / M&A / Shutdowns)
## New entities added this week
## Concept gaps flagged
## Gardener changes applied
```
