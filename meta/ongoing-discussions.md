---
type: meta
name: Ongoing discussions
updated: 2026-10-08
---

# Ongoing discussions

Unresolved design work shared across Claude Code sessions. Update an existing section as
the reasoning develops. Once the owner accepts a decision, record it in `DESIGN.md` (or the
more specific permanent document) and remove the section from this file.

## Source delivery to collectors

**Status:** Exploring — blocks collector implementation.

**Current direction:** Use a dedicated Gmail account for email-only newsletters, an RSS
aggregator such as Miniflux or Feedbin for feeds, and direct URL fetching for a small set of
known pages.

**Unresolved:**

- Hosted versus self-hosted RSS aggregation.
- How collectors authenticate to Gmail and the aggregator.
- Where source snapshots and failed captures are queued.

**Next step:** Compare the operational burden and API support of Miniflux and Feedbin.

## Scraping and web-search as collector modalities

**Status:** Leaning resolved — owner has not yet confirmed dropping Twitter/Reddit.

**Current direction:** Do not add Twitter/X or Reddit as recurring Stage 1 collectors, and
do not use the web-search tool as a Stage 1 collector modality at all. Reasons:

- Twitter/X has no free API tier; scraping is ToS-prohibited and carries account-ban risk.
- Reddit's free API has tightened and scraping is increasingly rate-limited; both are
  fragile for an unattended daily job.
- A web-search call is a point-in-time query, not a subscription — it can't answer "what's
  new since last run" without an LLM re-deduping every result against the whole vault each
  time, which reintroduces the cross-agent dedup problem §7 of `DESIGN.md` was designed to
  avoid.
- RSS/Atom and documented APIs (already the ~20 sources in `meta/sources.md`, all free)
  give a stable incremental-fetch contract with no ban risk, at zero cost.

**Where scraping / web-search still fit, outside Stage 1:**

- One-off manual backfill (e.g. pulling historical layoffs.fyi entries), not a scheduled
  collector.
- On-demand gap-filling inside Enrich or Gardener — e.g. a web-search call triggered when a
  company/concept note is flagged thin — rather than a new recurring ingestion stream.
- Sources with no feed but a stable page structure (YC directory, layoffs.fyi) are already
  marked `scrape (avoid; only if no alternative and ToS permits)` in `meta/sources.md` —
  consistent with this reasoning.

**Next step:** Owner to confirm dropping Twitter/Reddit from the source list entirely; if
confirmed, record in `DESIGN.md` §7 and remove this section.

## Production scheduling

**Status:** Deferred until the local pipeline is stable.

**Alternatives:** Cloud routines or a local scheduler.

**Next step:** Revisit after the collectors, Triage, Enrich, Gardener, and Digest stages
have been exercised locally.

## Paid company-data APIs

**Status:** Deferred.

Crunchbase or PitchBook may improve deal-sourcing coverage, but their cost is not justified
until real usage demonstrates a coverage gap.

**Next step:** Measure gaps using public sources before evaluating paid APIs.

## Initial tracked set

**Status:** Partially implemented.

The vertical slice exists, but the full starter set of concepts, threads, and seed
companies remains open.

**Next step:** Expand in reviewable batches while exercising the Enrich conventions.
