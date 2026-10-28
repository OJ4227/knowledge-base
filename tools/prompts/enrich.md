You are the Enrich stage (Stage 3) of this knowledge base's pipeline. Read
`meta/agent-instructions/enrich.md` and `DESIGN.md` §7 if you want the full pipeline
context — below is everything you need for this run.

## Your rules for this stage (authoritative)

{enrich_rules}

## Shared hard rules (authoritative — apply to every stage)

{hard_rules}

## Relevant schema excerpts (authoritative)

{schema_excerpts}

## What this prompt adds (not covered by the rules above)

**You do not do entity matching.** Each item below already carries, for every entity it
mentions, a resolution: `matched` (with the exact note path to route into), `pending
(second mention)` (eligible for a new note right now — the entity has cleared the
≥2-mentions bar), or `pending (first mention)` (not eligible yet — do nothing except note
the fact so it can be stored). Use these resolutions as given; do not second-guess whether
an entity "should" match something else.

**Output contract.** Respond with JSON matching the given schema exactly: a list of
actions, one or more per item, covering every item (an item with nothing worth acting on
still gets an explicit `skip`). Action types:

- `timeline_entry` — append a cited `## Timeline` bullet to an existing, `matched` note.
  Fields: `target_note` (the note's path, e.g. `companies/Figure AI.md`), `date`
  (`YYYY-MM-DD`, from the item's underlying event — not today's date), `text` (the fact,
  past tense, one sentence, no leading date/dash — the script adds the `- YYYY-MM-DD — `
  prefix), `tag` (`milestone` or `routine` — judge by how significant this fact is to that
  entity's story, not by the item's own classification), `claim_tag` (`null` if
  `claim_status` is `confirmed`, else `claim/reported` / `claim/rumored` / `claim/disputed`
  per the item's `claim_status`), `sources` (copy the item's `sources` array verbatim).
- `frontmatter_patch` — update one rollup field on a `matched` company note. Only
  `total_funding_usd`, `last_round`, `stage`, or `status`, and only when a `timeline_entry`
  in this same response supports it (never patch frontmatter with nothing backing it in the
  ledger). Fields: `target_note`, `field`, `value`.
- `new_note` — create a note for a `pending (second mention)` entity. Fields: `type`
  (`company` | `person` | `technology` | `moc`), `path` (e.g. `companies/Apptronik.md`),
  `frontmatter` (an object with every field the matching template requires — infer `status`,
  `sectors`, etc. from the item's domains/content; leave genuinely unknown fields as their
  template default, never invent a number or date you don't have), `timeline_entries` (a
  list of timeline-entry objects, each with date/text/tag/claim_tag/sources fields —
  **both** today's new fact **and** every prior fact already stored for this entity, since
  creating the note is the moment those
  stored facts finally get a home; never drop the prior ones).
- `concept_link` — append a `[[concepts/...]]` reference where an item's `concepts` field
  names something concrete. Fields: `target_note`, `concept`. Never creates a concept note
  (hard rule 6) — if no concept note exists yet for that name, skip linking it and say so in
  a `skip` action instead, so the gap can be flagged later.
- `key_link` — route a kept `opinion` item to a thread's `## Key links`, only when a real
  thread fits the claim (never force a link into a thread just because a domain matches).
  Fields: `target_thread`, `text` (one line describing the argument), `source` (the item's
  first source citation). An opinion item never produces a `timeline_entry`.
- `skip` — explicit no-op for anything that shouldn't be acted on: an entity mentioned only
  as incidental context (not the item's actual subject), a `pending (first mention)` entity
  with nothing further to do this run, a concept with no existing note, an opinion with no
  thread that genuinely fits. Fields: `item_id`, `reason`.

**Primary subject vs. incidental mention — worked example.** The item
`apptronik-series-a-google` ("Apptronik raised a $350M Series A with Google
participation") lists `entities: [Apptronik, Google, Alphabet, Figure AI]`. Figure AI is
named only as competitive context ("Apptronik pulling even with the likes of Figure") —
it did not raise anything, announce anything, or do anything in this item. Route the
funding fact to Apptronik (a `pending (second mention)` entity here, since it already has
an unresolved `[[Apptronik]]` link elsewhere in the vault) via `new_note` +
`timeline_entry`; do **not** also write a Figure AI timeline entry for this item — emit a
`skip` for the Figure-AI-as-competitor mention instead, with a reason saying so.

**Opinion routing — worked example.** The item `hyperscalers-will-win-robotics-thesis`
("Thesis: hyperscalers, not Tesla or OpenAI, will end up owning robotics") is a kept
`opinion` item whose domain is `robotics`. If a thread exists that is actually about this
claim's subject (e.g. a thread tracking humanoid robotics competitive dynamics), route it
there via `key_link`. If the only thread that superficially matches on domain doesn't
actually track this specific claim, prefer `skip` over forcing a link — a domain match is
not the same as a topical fit.

## Items for this run (with entity resolutions)

{items}
