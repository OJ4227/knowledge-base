---
type: meta
name: Ongoing discussions
updated: 2026-10-08
---

# Ongoing discussions

Unresolved design work shared across Claude Code sessions. Update an existing section as
the reasoning develops. Once the owner accepts a decision, record it in `DESIGN.md` (or the
more specific permanent document) and remove the section from this file.

## Production scheduling

**Status:** Deferred until the local pipeline is stable.

**Alternatives:** Cloud routines or a local scheduler.

**Next step:** Revisit after the collectors, Triage, Enrich, Gardener, and Digest stages
have been exercised locally.

## Collector implementation details

**Status:** Exploring — source-delivery tooling is now decided (Readwise Reader + Tavily +
YouTube transcripts, see `DESIGN.md` §7); these are the remaining before-code questions.

**Unresolved:**

- How `collect-readwise`, `collect-tavily`, and the other collector scripts store API keys
  (env vars vs. a local secrets file, kept out of Git either way).
- Where source snapshots and failed captures are queued for review.
- The initial Tavily query list: which threads/domains get a daily date-bounded query, kept
  small enough to stay inside the 1,000-credit/month free tier.
- The initial YouTube channel/video list to track.

**Next step:** Settle these while building the first collector (`collect-readwise`, since it
covers the most sources).

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
