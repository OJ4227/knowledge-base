---
type: meta
name: Gardener instructions
updated: 2026-10-28
---

# Gardener (Stage 5, weekly; deep sweep monthly)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.

- Consume `meta/health/lint-report.md`.
- Auto-apply (and log): unlinked-mention linking, `related:` links, MOC membership,
  alias registration, obvious internal-link fixes.
- Propose (to `meta/review/`): note merges, deletions, restructures, non-trivial concept
  rewrites.
- Maintain `## State of the art` / `## Current state` blocks.
- Repair dead external links (replacement URL, or `[dead-link]` + archive.org fallback).
- Rotate timelines per `DESIGN.md` §9.
- Write `meta/health/report.md` (stats, orphans [see `meta/agent-instructions/lint.md` —
  excludes concepts and seed notes], stubs, stale entities, concept gaps, coverage gaps).
