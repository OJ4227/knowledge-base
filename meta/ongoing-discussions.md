---
type: meta
name: Ongoing discussions
updated: 2026-10-13
---

# Ongoing discussions

Unresolved design work shared across Claude Code sessions. Update an existing section as
the reasoning develops. Once the owner accepts a decision, record it in `DESIGN.md` (or the
more specific permanent document) and remove the section from this file.

## Production scheduling / collector hosting

**Status:** Deferred until the local pipeline is stable, but the shape of the eventual
answer is now clearer.

`collect-readwise` is a batch job (wakes up, fetches what's new, writes files, exits), not
a long-running service — it does **not** require leaving a laptop plugged in and running.
Running it locally now (manually, or via `cron`/`launchd` whenever convenient) is fine for
prototyping: if a run is skipped, nothing is lost, since the watermark just picks up a wider
window next time. The committed `meta/collector-state.json` watermark (see `HANDOVER.md`)
was specifically designed so switching from a local machine to an always-on runner later
doesn't require migrating state — whichever runner does a `git pull` picks up exactly where
the last run left off.

**Alternatives for the always-on runner:** GitHub Actions (free scheduled workflows; this
repo already has a GitHub remote) or the "Claude cloud routines" `DESIGN.md` §7/§12 already
names as the target.

**Next step:** Revisit once the collectors, Triage, Enrich, Gardener, and Digest stages have
been exercised locally — then choose between GitHub Actions and Claude cloud routines and
wire up the schedule.

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
- Which public Twitter/X Lists to subscribe to via Readwise (see `DESIGN.md` §7) — needs
  curating (e.g. "AI researchers," "robotics founders"), and owner confirmation that
  Readwise's Twitter integration (flagged experimental by Readwise itself) behaves as
  expected before treating it as more than a bonus feed.

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
