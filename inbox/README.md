---
type: meta
name: Inbox
updated: 2026-08-30
---

# inbox/

Agent working area. Collectors drop raw captures here; Triage consumes and clears them.

- **Raw capture** (from a collector): `YYYY-MM-DD-<slug>--capture.md` — one newsletter/
  article item, linked to its `[[sources/...]]` note, minimally extracted, not yet
  classified. A single capture file commonly bundles several independent developments.
- **Triage output**: `inbox/_triage/YYYY-MM-DD.json` — one run, fanned out into one
  classified item per development (not per input file), deduped across streams, each
  citing one or more `[[sources/...]]`. Raw captures consumed by the run are deleted.
  Consumed by Enrich, not a vault note itself — `tools/prompts/triage.md` and
  `tools/triage.py` define the schema.

Nothing here is permanent. If the inbox is not empty, the pipeline has unfinished work.
Hand-review anything that has lingered more than a few days.
