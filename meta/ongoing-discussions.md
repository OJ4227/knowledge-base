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
