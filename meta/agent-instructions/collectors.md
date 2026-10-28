---
type: meta
name: Collectors instructions
updated: 2026-10-28
---

# Collectors (Stage 1, per source modality)

Shared hard rules: `meta/agent-instructions/hard-rules.md`. Full rationale: `DESIGN.md` §7.

- Fetch from one source modality (newsletters / RSS / GitHub releases / filings).
- For each item: create a `sources/` note (from the template), submit the URL to
  web.archive.org, save a local snapshot to `sources/_snapshots/`, set `archive_url` and
  `local_copy`.
- Emit a raw capture into `inbox/` as a dated file, linked to its source note. Light
  extraction only — no classification, no routing.
- Structured sources (RSS, GitHub, EDGAR) run as scripts with no LLM.
