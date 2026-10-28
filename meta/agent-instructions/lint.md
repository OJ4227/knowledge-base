---
type: meta
name: Lint instructions
updated: 2026-10-28
---

# Lint (`tools/lint.py`, every commit + nightly)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.

Detection only, never edits. Writes `meta/health/lint-report.md`. Exit 1 on any error
(or, with `--strict`, any warning). See `tools/README.md` to run it.

**Errors (fail the run):**

- Invalid or missing frontmatter; unknown `type`
- Missing required fields, bad enum values, bad date formats (per `schema.md`)
- Broken `[[sources/...]]` citation — resolves to no source note (accounting for aliases)
- Uncited dated `## Timeline` entry in a non-`seed` note

**Warnings (reported, non-blocking):**

- `unresolved-link` — a non-source `[[link]]` with no target. Expected in quantity: every
  `[[Competitor]]` / `[[future concept]]` marker shows here until that note exists. Review
  periodically; never create a link or note just to clear one.
- `missing-section`, `unknown-sector`, `stub`, `stale-watchlist`, `missing-archive`
- `unsupported-volatile-field` — a non-`seed` company has `stage` / funding set but no
  cited `## Timeline` entry. Heuristic; true fact-to-source verification is a human job.
- `orphan` — see below.

**Not yet implemented** (need git-diff or network access — added with the pipeline):
curated-block tamper detection, dead external-link checking.

**Orphans** — a note with no inbound links. This is a weak signal, not a defect to fix.
Exclude from the orphan list:

- `type: concept` — concept notes are lookup targets, reached via search and the
  `Concepts index` dashboard, not via links. An unlinked concept is normal.
- `seed: true` notes — the surrounding graph has not been built yet; expected.

Report the remaining orphans (companies, people, technologies, threads with nothing
pointing at them) so the gardener can consider a link *if a real relationship exists* —
never add a link solely to clear orphan status.
