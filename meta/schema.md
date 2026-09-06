---
type: meta
name: Schema
updated: 2026-08-30
---

# Note schemas

Authoritative field definitions for every note type. The `lint` script validates against
this. Changing a schema means updating this file, the matching template in `templates/`,
and the lint rules in the same commit.

## Conventions (all types)

- **Dates:** ISO 8601 (`YYYY-MM-DD`), or `YYYY` / `YYYY-MM` where only that precision is known.
- **Links:** `[[wikilinks]]` for every entity mention, in frontmatter and body.
  `newLinkFormat` is "shortest" — link by note name, not path, unless disambiguating.
- **Facets** (sectors, categories, domains) go in **frontmatter lists**, not tags.
- **Tags** are only for cross-cutting workflow state, e.g. `#deal-flow/contacted`,
  `#needs-review`.
- **Curated blocks** are marked `<!-- curated -->`. Agents never edit these except the
  single designated `## State of the art` / `## Current state` block per tracked note.
- `created` is set once; `updated` is bumped on every material change.
- `seed: true` (optional, any tracked type) — the note was created by hand before the
  collector/enrich pipeline existed. Its facts may be uncited and its `## Timeline` thin.
  The gardener lists seed notes in the health report for citation backfill; remove the flag
  once the note has been reconciled against real sources.
- **Dataview:** every analytics query excludes `templates/` and `meta/` in its `FROM`
  clause (e.g. `FROM "" AND -"templates" AND -"meta"`). Template files carry real `type:`
  values and would otherwise be indexed as notes.

## `concept`

Evergreen explainer. Curated end to end. No mandatory timeline.

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `concept` | |
| `name` | ✓ | string | |
| `aliases` | | list[string] | other names / acronyms |
| `category` | ✓ | enum | `protocol` \| `architecture` \| `technique` \| `infra` \| `eval` \| `primitive` \| `pattern` |
| `related` | | list[link] | other concepts |
| `maturity` | ✓ | enum | `emerging` \| `established` \| `contested` \| `fading` |
| `created` / `updated` | ✓ | date | |

Body sections: `## Definition`, `## How it works`, `## Why it matters`,
`## Variants / alternatives`, `## Related concepts`, `## Developments` (optional, links
only), `## Sources`.

## `company`

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `company` | |
| `name` | ✓ | string | |
| `aliases` | | list[string] | |
| `status` | ✓ | enum | `active` \| `stealth` \| `acquired` \| `shut-down` |
| `founded` | | year | |
| `hq` | | string | "City, Country" |
| `sectors` | ✓ | list[string] | controlled vocab — see `taxonomy.md` |
| `stage` | | enum | `pre-seed` \| `seed` \| `series-a` \| `series-b` \| `series-c` \| `series-d+` \| `public` \| `bootstrapped` |
| `total_funding_usd` | | number | integer USD |
| `last_round` | | object | `{type, amount_usd, date, lead: list[string]}` |
| `people` | | list[link] | `[[person]]` notes |
| `watchlist` | ✓ | bool | drives dashboards |
| `priority` | | enum | `high` \| `medium` \| `low` — deal-sourcing signal |
| `created` / `updated` | ✓ | date | |

Body: `## Summary` (curated), `## What they do` (curated), `## Key milestones`
(curated/gardener), `## Timeline` (append-only, cited), `## Funding history`, `## People`,
`## Competitors`, `## Open questions`.

Every value in `total_funding_usd`, `last_round`, `stage`, `status` must be supported by a
cited `## Timeline` entry. Lint cross-checks.

## `person`

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `person` | |
| `name` | ✓ | string | |
| `aliases` | | list[string] | |
| `role` | | string | current title |
| `current_company` | | link | |
| `past_companies` | | list[link] | |
| `notable_for` | | string | one line |
| `created` / `updated` | ✓ | date | |

Body: `## Summary` (curated), `## Timeline` (append-only, cited), `## Links`.

## `technology`

Specific tracked artefact with a lifecycle.

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `technology` | |
| `name` | ✓ | string | |
| `aliases` | | list[string] | |
| `category` | ✓ | enum | `model` \| `hardware` \| `robot` \| `framework` \| `benchmark` |
| `status` | ✓ | enum | `announced` \| `released` \| `deprecated` \| `vaporware` |
| `first_seen` | ✓ | date | |
| `key_orgs` | | list[link] | |
| `concepts` | | list[link] | `[[concepts/...]]` it implements / depends on |
| `related` | | list[link] | |
| `maturity` | ✓ | enum | `emerging` \| `scaling` \| `mainstream` \| `superseded` |
| `created` / `updated` | ✓ | date | |

Body: `## What it is` (curated), `## Why it matters` (curated), `## State of the art`
(gardener), `## Timeline` (append-only, cited), `## Key links`.

## `moc` (topic / thread)

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `moc` | |
| `name` | ✓ | string | |
| `aliases` | | list[string] | |
| `kind` | ✓ | enum | `thread` (running narrative) \| `index` (pure MOC) |
| `domains` | | list[enum] | `ai` \| `robotics` \| `hardware/compute` \| `business` |
| `concepts` | | list[link] | |
| `related` | | list[link] | |
| `created` / `updated` | ✓ | date | |

Body: curated intro, `## Current state` (gardener), `## Timeline` (append-only),
`## Key entities` (Dataview), `## Key links`.

## `source`

| Field | Req | Type | Notes |
|---|---|---|---|
| `type` | ✓ | `source` | |
| `title` | ✓ | string | |
| `publication` | ✓ | string | |
| `authors` | | list[string] | |
| `published` | ✓ | date | |
| `accessed` | ✓ | date | |
| `url` | ✓ | string | |
| `archive_url` | ⚠ | string | web.archive.org snapshot; missing → `missing-archive` warning, not an error |
| `local_copy` | | string | path under `sources/_snapshots/` |
| `tier` | ✓ | enum | `primary` \| `secondary` \| `tertiary` |
| `superseded_by` | | link | set if retracted / corrected |

Body: `## Extract` (quoted passage). **Immutable once written.**

`archive_url` is expected but not blocking — a source can be created before its archival
step runs (build step 5). The [[Provenance audit]] dashboard and the `missing-archive`
lint warning track the gap.

## Timeline entry format

```
- YYYY-MM-DD — <fact, past tense, one sentence>. ([[sources/<slug>]]) #milestone
```

- Newest first, under a `### YYYY` heading.
- `#milestone` or `#routine` on every entry (drives log rotation — see `DESIGN.md` §9).
- One or more `[[sources/...]]` citations, always.
- Claim status when not `confirmed`: add a tag — `#claim/reported`, `#claim/rumored`, or
  `#claim/disputed` — so the [[Provenance audit]] dashboard can surface it. For `disputed`,
  state both versions with attribution in the entry text.

Example:

```
### 2024
- 2024-02-29 — Raised $675M Series C, led by [[OpenAI]] and [[Microsoft]]. ([[sources/2024-02-29-the-batch-figure]]) #milestone
- 2024-01-31 — Reported to be raising at a ~$2.6B valuation. ([[sources/2024-01-31-bloomberg-figure]]) #routine #claim/rumored
```
