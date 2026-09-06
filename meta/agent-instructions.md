---
type: meta
name: Agent instructions
updated: 2026-08-30
---

# Agent instructions

Operating rules for the automated pipeline. These govern the pipeline agents and routine
maintenance sessions — **not** owner-directed build/scaffolding work. When `CLAUDE.md` is
added (build step 7) it will be a short pointer to this file plus the hard rules below.

Read `DESIGN.md` for the full rationale.

## Hard rules — never break these

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

## Pipeline stages

### Collectors (Stage 1, per source modality)

- Fetch from one source modality (newsletters / RSS / GitHub releases / filings).
- For each item: create a `sources/` note (from the template), submit the URL to
  web.archive.org, save a local snapshot to `sources/_snapshots/`, set `archive_url` and
  `local_copy`.
- Emit a raw capture into `inbox/` as a dated file, linked to its source note. Light
  extraction only — no classification, no routing.
- Structured sources (RSS, GitHub, EDGAR) run as scripts with no LLM.

### Triage (Stage 2, daily, one LLM context)

- Read all `inbox/` raw captures.
- Deduplicate across all streams in this single context (same event from 3 newsletters = 1
  capture with 3 source links).
- Classify each on both taxonomy axes (`meta/taxonomy.md`).
- Drop noise (opinion with no event, pure marketing, already-known facts).
- Flag recurring unfamiliar terms as concept-note gaps.
- Emit clean classified captures; remove processed raw captures from `inbox/`.

### Enrich (Stage 3, daily, one LLM context)

- Route each classified capture to the relevant `company` / `technology` / `topic` note(s),
  and add `[[concepts/...]]` links where a concept is touched.
- Append a `## Timeline` entry per the format in `meta/schema.md`, tagged `#milestone` or
  `#routine`, with source citation(s).
- Update frontmatter rollups (`total_funding_usd`, `last_round`, `stage`, `status`,
  `updated`) — only where a new cited timeline entry supports it.
- Create new tracked notes only under rule 5, from `templates/`.
- Never touch curated blocks. Never edit concept bodies.

### Gardener (Stage 4, weekly; deep sweep monthly)

- Consume `meta/health/lint-report.md`.
- Auto-apply (and log): unlinked-mention linking, `related:` links, MOC membership,
  alias registration, obvious internal-link fixes.
- Propose (to `meta/review/`): note merges, deletions, restructures, non-trivial concept
  rewrites.
- Maintain `## State of the art` / `## Current state` blocks.
- Repair dead external links (replacement URL, or `[dead-link]` + archive.org fallback).
- Rotate timelines per `DESIGN.md` §9.
- Write `meta/health/report.md` (stats, orphans [see Lint note — excludes concepts and
  seed notes], stubs, stale entities, concept gaps, coverage gaps).

### Digest (Stage 5, weekly)

Write `digests/YYYY-WW.md`:

```
## Technical developments   (AI / Robotics / Compute-hardware)
## Threads that moved
## Business                 (Funding / People / M&A / Shutdowns)
## New entities added this week
## Concept gaps flagged
## Gardener changes applied
```

## Lint (`tools/lint.py`, every commit + nightly)

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
