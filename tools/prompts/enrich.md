You are the Enrich stage (Stage 3) of this knowledge base's pipeline. Read
`meta/agent-instructions/enrich.md` and `DESIGN.md` §7 if you want the full pipeline
context — below is everything you need for this run.

## Your rules for this stage (authoritative)

{enrich_rules}

## Shared hard rules (authoritative — apply to every stage)

{hard_rules}

## Relevant schema excerpts (authoritative)

{schema_excerpts}

## Company sector vocabulary (authoritative)

{sector_vocabulary}

## What this prompt adds (not covered by the rules above)

**You do not do entity matching.** Each item below already carries, for every entity it
mentions, a resolution: `matched` (with the exact note path to route into), `pending
(second mention)` (eligible for a new note right now — the entity has cleared the
≥2-mentions bar), or `pending (first mention)` (not eligible yet — if the item reports a
real, citable fact about this entity, emit a `pending_fact` action so it's stored until a
second mention arrives; if the entity is only incidental context with nothing citable,
`skip` instead). Use these resolutions as given; do not second-guess whether an entity
"should" match something else.

**Output contract.** Respond with JSON matching the given schema exactly. The response has
seven required top-level arrays: `timeline_entries`, `frontmatter_patches`, `new_notes`,
`concept_links`, `key_links`, `pending_facts`, and `skips`. Include every array even when it
is empty. Put one or more records across those arrays for every item; an item with nothing
worth acting on gets an explicit record in `skips`. Every record carries `item_id`; records
that edit or create a note also carry `target_note`.

- `timeline_entries` — append cited `## Timeline` bullets to existing, `matched` notes.
  Each record has `item_id`, `target_note`, and nested `timeline_entry`: `date`
  (`YYYY-MM-DD`, from the item's underlying event —
  not today's date), `text` (the fact, past tense, one sentence, no leading date/dash — the
  script adds the `- YYYY-MM-DD — ` prefix), `tag` (`milestone` or `routine` — judge by how
  significant this fact is to that entity's story, not by the item's own classification),
  `claim_tag` (use `""` if `claim_status` is `confirmed`, else `claim/reported` /
  `claim/rumored` / `claim/disputed` per the item's `claim_status`), `sources` (copy the
  item's `sources` array verbatim).
- `frontmatter_patches` — update rollup fields on `matched` company notes. Each record has
  `item_id`, `target_note`, and nested `frontmatter_patch`. Only
  `total_funding_usd`, `last_round`, `stage`, or `status`, and only when a `timeline_entry`
  in this same response supports it (never patch frontmatter with nothing backing it in the
  ledger). The nested object contains `field` and `value`.
- `new_notes` — create notes for `pending (second mention)` entities. Each record has
  `item_id`, `entity` (the exact item entity), `target_note` (for example
  `companies/Apptronik.md`), and nested `new_note`: `type` (`company` | `person` |
  `technology` | `moc`), `frontmatter_yaml` (a YAML mapping with every field the template
  requires — use only the company sector vocabulary above, never copy capture domains such
  as `ai`, `business`, or `hardware/compute` into `sectors`; infer `status`, `sectors`,
  etc. from the item's content; leave
  genuinely unknown fields as their template default, never invent a number or date you
  don't have), `timeline_entries` (a list of timeline-entry objects, each with
  date/text/tag/claim_tag/sources fields — **both** today's new fact **and** every prior
  fact already stored for this entity, since creating the note is the moment those stored
  facts finally get a home; never drop the prior ones). If an `opinion` item is the second
  mention, it may trigger note creation only when a real prior fact is supplied in the
  resolution; include those prior facts verbatim and add no timeline entry from the
  opinion itself. If there is no prior stored fact, use `skips` instead.
- `concept_links` — append `[[concepts/...]]` references where an item's `concepts` field
  names something concrete. Each record has `item_id`, `target_note`, and `concept`. Never
  creates a concept note
  (hard rule 6) — if no concept note exists yet for that name, skip linking it and say so in
  a `skips` record instead, so the gap can be flagged later.
- `key_links` — route kept `opinion` items to threads' `## Key links`, only when a real
  thread fits the claim (never force a link into a thread just because a domain matches).
  Each record has `item_id`, `target_note` (the thread's note path), and nested `key_link`:
  `text` (one line describing the argument), `source` (the item's first source citation).
  An opinion item never produces a timeline entry.
- `pending_facts` — store cited facts about `pending (first mention)` entities so they
  survive until a second mention clears the ≥2-mentions bar (no note is created yet).
  Each record has `item_id`, `entity` (the exact item entity), and a required nested
  `timeline_entry`, populated exactly like records in `timeline_entries`. Example:
  `{{"item_id": "<item id>", "entity": "Nvidia",
  "timeline_entry": {{"date": "2025-09-25", "text": "Participated in Figure AI's ~$39B Series
  C round.", "tag": "routine", "claim_tag": "", "sources":
  ["[[sources/<slug>]]"]}}}}`. Never used for an
  opinion item (opinions produce no storable fact, pending or otherwise).
- `skips` — explicit no-ops for anything that shouldn't be acted on: an entity mentioned only
  as incidental context (not the item's actual subject, nothing citable about it), a
  concept with no existing note, an opinion with no thread that genuinely fits. Fields:
  `item_id`, `reason`. Prefer consolidating several same-reason incidental entities from one
  item into a single `skip` action over one per entity — the `reason` text is for human
  review, not a per-entity record.

**Primary subject vs. incidental mention — worked example.** The item
`apptronik-series-a-google` ("Apptronik raised a $350M Series A with Google
participation") lists `entities: [Apptronik, Google, Alphabet, Figure AI]`. Figure AI is
named only as competitive context ("Apptronik pulling even with the likes of Figure") —
it did not raise anything, announce anything, or do anything in this item. Route the
funding fact to Apptronik (a `pending (second mention)` entity here, since it already has
an unresolved `[[Apptronik]]` link elsewhere in the vault) via a `new_notes` record; do
**not** also write a Figure AI timeline entry for this item — emit a `skips` record for the
Figure-AI-as-competitor mention instead, with a reason saying so. Google and
Alphabet are `pending (first mention)` here, but each has a real citable fact (participated
in the round / announced the partnership) — emit a `pending_facts` record for each, not a
skip.

**Opinion routing — worked example.** The item `hyperscalers-will-win-robotics-thesis`
("Thesis: hyperscalers, not Tesla or OpenAI, will end up owning robotics") is a kept
`opinion` item whose domain is `robotics`. If a thread exists that is actually about this
claim's subject (e.g. a thread tracking humanoid robotics competitive dynamics), route it
there via `key_links`. If the only thread that superficially matches on domain doesn't
actually track this specific claim, prefer `skips` over forcing a link — a domain match is
not the same as a topical fit.

## Items for this run (with entity resolutions)

{items}
