---
type: meta
name: Inbox
updated: 2026-08-30
---

# inbox/

Agent working area. Collectors drop raw captures here; Triage consumes and clears them.

- **Raw capture** (from a collector): `YYYY-MM-DD-<slug>.md` — one candidate development,
  linked to its `[[sources/...]]` note, minimally extracted, not yet classified.
- **Classified capture** (from Triage): same file, now with domain + development-type tags
  and dedup links, awaiting Enrich.

Nothing here is permanent. If the inbox is not empty, the pipeline has unfinished work.
Hand-review anything that has lingered more than a few days.
