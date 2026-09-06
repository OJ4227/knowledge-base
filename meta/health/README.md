---
type: meta
name: Health reports
updated: 2026-09-05
---

# meta/health/

Agent- and tool-generated. **Not committed** (git-ignored) — regenerated on demand.

- **`lint-report.md`** — latest output of `tools/lint.py` (errors + warnings). Rewritten
  every run.
- **`report.md`** — latest gardener health report (vault stats, coverage gaps, concept-note
  gaps, stub notes, stale entries, orphans). Rewritten weekly.

If a file is missing, run the tool: `.venv/bin/python tools/lint.py` regenerates
`lint-report.md`.
