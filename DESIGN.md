# AI / Robotics / Startups Knowledge Base — Design & Intent

The design record for this vault. Read it before working on the vault's architecture, its
agents, or its tooling. If you change the design, update this file in the same commit.

**Status: design agreed, not yet scaffolded (2026-08-30).** See §11 and §12.

No `CLAUDE.md` exists yet — it is deferred to the end of the build (§12 step 7) so its
operating rules don't interfere with scaffolding. Until then, this file is the entry point;
read it in full before working on the vault.

---

## 1. Purpose

A markdown knowledge base covering **AI, robotics, and the startups / growing companies**
in those industries. Viewed in **Obsidian**. Populated largely by **automated agents** from
a curated set of trusted sources, plus hand-curated reference material.

Primary uses, in priority order:

1. **Reference knowledge store.** Two kinds:
   - *Evergreen concepts* — how modern AI / LLM systems actually work: MCP, inference and
     serving layers, RAG, agent architectures, context engineering, quantization,
     speculative decoding, eval methods, and so on. This is foundational understanding, not
     news, and much of it is not new.
   - *Current-state lookups* — "what is the latest on technology X / thread Y".
2. **Trend & change tracking** — how companies, technologies, and themes evolve over time.
3. **Deal / opportunity sourcing** — track startups for investment / partnership / scouting.

It must keep the owner up to date on **technological developments**, not just business
events — technical progress is a first-class stream.

Mental model: an **AI wiki** — atomic pages, heavy interlinking, Maps of Content (MOCs),
and "infoboxes" implemented as YAML frontmatter.

**Single vault, not several.** Concepts, tracked technologies, threads, companies, and
people all live in one repo, separated by folder and `type:`. The cross-linking between
them is the core value, and Obsidian has no good cross-vault linking. If concepts ever need
to be published standalone, that is an export problem to solve then, not a reason to
fragment now.

---

## 2. Core principles

These shape every agent and script. Do not violate them without an explicit decision
recorded here.

- **Detect with scripts, repair with LLMs.** Mechanical, deterministic work (link checking,
  schema validation, RSS parsing, structured-data ingestion) is plain code — run often,
  cheap. LLM agents are reserved for judgment: extraction from prose, dedup decisions,
  link suggestions, curated-summary writing, concept drafting.

- **Event ledger vs derived state** (applies to *tracked* notes — companies, technologies,
  threads). Each such note is an append-only event ledger (the `## Timeline`) plus derived
  state (frontmatter + curated prose). Trust lives in the ledger; frontmatter is a rollup
  of it. This is event-sourcing for a wiki.

- **Concepts are the exception** — evergreen explainers, refined in place, no mandatory
  timeline. See §5.

- **Immutable timeline.** Timeline entries are never rewritten or silently deleted. They may
  be *moved* to a linked archive note (log rotation — see §9). Corrections are new entries,
  not edits.

- **Additive changes auto-apply; destructive changes are proposed.** Agents may add links,
  aliases, MOC memberships, `related:` entries, and cited timeline bullets on their own
  (logged in the weekly digest). Merges, deletions, content removal, and restructuring go
  to a human review queue (`meta/review/`).

- **Every agent-written fact in a tracked note is cited.** No uncited timeline bullets; no
  frontmatter fact without a supporting cited timeline entry. Lint enforces this.

- **Curated sections are off-limits to agents** except the one designated
  `## State of the art` / `## Current state` block per tracked note. Concept notes are
  curated end to end; agents draft and propose, the owner approves.

- **Grow by relevance, not by target.** A tracked entity gets its own note only when it has
  ≥2 independent mentions or the owner flags it. This is the main defense against bloat.

---

## 3. Repo / vault structure

```
knowledge-base/
├── concepts/             # evergreen explainers of how modern AI/LLM systems work
├── companies/            # one atomic note per company
│   └── _timeline/         # rotated timeline archives (see §9)
├── people/               # founders, key operators, notable researchers
├── technologies/         # specific tracked things with a lifecycle:
│                         #   models (Claude 4), hardware (GB200), robots (Figure 02),
│                         #   frameworks, benchmarks
├── topics/               # MOCs and "threads" — long-running narratives (see §6)
├── inbox/                # agent drop zone: unprocessed raw captures
├── sources/              # one note per source item (provenance)
│   └── _snapshots/        # local archived copies of source content
├── digests/              # weekly "what changed" summaries
├── dashboards/           # Dataview queries
├── templates/            # static note skeletons (one per type)
└── meta/                 # schema.md, taxonomy.md, agent-instructions.md,
                          # sources.md, rejected-links.md, health/, review/
```

Three reference layers, all in one vault:

- **`concepts/`** — evergreen. "MCP", "inference layer", "KV cache", "RAG". Stable.
- **`technologies/`** — specific tracked artefacts with a lifecycle and a timeline.
- **`topics/`** — threads: narratives that accumulate developments over time.

Everything links back to the concept layer.

The vault **is** the git repo. `.obsidian/` is committed so config is portable.

---

## 4. Note types & schemas

Full schemas will live in `meta/schema.md`. Summary:

**concept** (`type: concept`) — `type, name, aliases, category (protocol|architecture|
technique|infra|eval|primitive|...), related[], maturity (emerging|established|contested|
fading), updated`.
Body, curated end to end: `## Definition` · `## How it works` · `## Why it matters` ·
`## Variants / alternatives` · `## Related concepts` · `## Developments` (optional — just
links out to the threads / technologies where change is tracked) · `## Sources`.
No mandatory `## Timeline`. Refined in place.

**company** — `type, name, aliases, status (active|stealth|acquired|shut-down), founded, hq,
sectors[], stage, total_funding_usd, last_round{type,amount_usd,date,lead[]}, people[],
watchlist, priority, created, updated`.
Body: `## Summary` (curated) · `## What they do` (curated) · `## Timeline` (agent-appended,
cited) · `## Funding history` · `## People` · `## Competitors` · `## Open questions` ·
`## Key milestones` (gardener-curated).

**person** — `type, name, aliases, role, current_company, past_companies[], notable_for`.

**technology** — `type, name, category (model|hardware|robot|framework|benchmark), status,
first_seen, key_orgs[], related[], concepts[], maturity, updated`.
Body: `## What it is` (curated) · `## Why it matters` (curated) ·
`## State of the art` (gardener-maintained) · `## Timeline` · `## Key links`.

**topic / MOC / thread** — `type: moc`. Curated intro + `## Current state`
(gardener-maintained) + running `## Timeline` of linked developments + embedded Dataview.

**source** — `type: source, title, publication, authors[], published, accessed, url,
archive_url, local_copy, tier (primary|secondary|tertiary), superseded_by?`.
Body: `## Extract` with the quoted passage(s). **Immutable once written.**

Conventions: ISO 8601 dates everywhere. `[[wikilinks]]` for every entity mention.
Frontmatter lists (not tags) for structured facets; tags only for cross-cutting workflow
state (e.g. `#deal-flow/contacted`). Curated blocks marked `<!-- curated -->`.

---

## 5. Concept notes — how they are populated

Different from the daily pipeline. Concept notes are the stable layer; the pipeline links
*to* them far more than it edits them.

- **On-demand.** The owner asks for a concept note; an agent researches and drafts it
  (cited), the owner curates and approves.
- **Gap detection.** When Triage / Enrich repeatedly encounters a term with no concept
  note, it flags it in `meta/health/report.md` for creation — it does not auto-create.
- **Linking, not editing.** The daily pipeline adds `[[concepts/...]]` links from
  developments; it does not rewrite concept bodies.
- **Refresh.** The gardener updates a concept's curated explanation only when the field
  genuinely shifts, and proposes non-trivial rewrites for review rather than applying them.
- Concept notes are sourced (a `## Sources` section) but not ledgered fact-by-fact — they
  are explainers, not audit trails.

---

## 6. Capture taxonomy

Every capture is classified on two axes (full list will be in `meta/taxonomy.md`):

**Domain:** `ai` · `robotics` · `hardware/compute` · `business`

**Development type:** `model-release` · `research` · `capability-demo` · `product` ·
`hardware` · `benchmark` · `open-source` · `funding` · `m&a` · `people-move` · `shutdown` ·
`policy`

Only ~4 of ~12 types are business events — technical developments dominate by design.

**Threads** are the "stay up to date" mechanism: `topics/` MOCs that are ongoing storylines
(e.g. *Humanoid manipulation*, *Test-time compute*, *Custom silicon vs NVIDIA*,
*On-device models*, *Agent reliability*). A capture links into the specific entity, the
relevant thread, and any concept it touches. To catch up on a subject, read one thread note
top-down.

---

## 7. The agent pipeline

Five stages. Target runtime: **Claude cloud routines committing to a GitHub repo**
(runs unattended; owner pulls into local Obsidian). Prototype prompts locally with
`/schedule` first, migrate once stable.

**Stage 1 — Collectors (one per source modality).** Fetch + light extraction into
`inbox/` as raw captures, each already linked to a freshly created `sources/` note.
- `collect-newsletters` — Gmail API, LLM (prose extraction needed)
- `collect-rss` — RSS/Atom via aggregator API (Miniflux / Feedbin), mostly a script
- `collect-github-releases` — script
- `collect-filings` — SEC EDGAR Form D, script
- No dedicated research-paper pipeline (see §8). Important papers arrive via newsletters
  and one aggregated pre-ranked feed (e.g. HF Papers weekly top).

Collectors also trigger archival: submit the URL to web.archive.org, save a local snapshot
to `sources/_snapshots/`.

**Stage 2 — Triage (one LLM agent, daily).** Reads all raw captures, applies the taxonomy
(§6) consistently, dedupes across streams in one context, emits clean classified captures.
Flags unfamiliar recurring terms as concept-note gaps.

**Stage 3 — Enrich (one LLM agent, daily).** Routes each capture to the relevant company /
technology / thread note(s) and adds `[[concepts/...]]` links. Appends dated, cited
`## Timeline` bullets tagged `milestone` or `routine`. Updates frontmatter rollups. Creates
new tracked notes from templates only under the "≥2 mentions or flagged" rule. Never
rewrites prose. Never touches curated blocks. Never edits concept bodies.

**Stage 4 — Gardener (LLM, weekly; deep sweep monthly).** Consumes the lint report and
scans the vault: dedup proposals, unlinked-mention linking, `related:` suggestions, MOC
membership, dead-link repair, refresh of `## State of the art` / `## Current state` blocks,
concept-explanation refresh proposals, timeline rotation (§9), and writes
`meta/health/report.md`. Additive fixes auto-apply and are logged; destructive ones go to
`meta/review/YYYY-WW.md`.

**Stage 5 — Digest (weekly).** Writes `digests/YYYY-WW.md`, split so technical signal is
not drowned by business noise:

```
## Technical developments  (AI / Robotics / Compute-hardware)
## Threads that moved
## Business  (Funding / People / M&A / Shutdowns)
## New entities added this week
## Concept gaps flagged
## Gardener changes applied
```

**Lint (script, every commit + nightly).** Deterministic detection only — fixes nothing.
Broken internal links, frontmatter schema violations, orphans, stubs, dead external links
(weekly), stale watchlist entries, curated-section tampering, uncited agent-added bullets,
frontmatter facts with no supporting cited entry. Hard errors fail the commit.

Orphans are a weak signal, not a defect: concept notes (lookup targets) and `seed: true`
notes are excluded, and a link is never added just to clear orphan status — see
`meta/agent-instructions.md`.

### Why the pipeline is shaped this way

- **Split ingest by source modality, never by domain or technical-vs-business.** Sources are
  cross-cutting (one newsletter issue carries model releases, funding, and policy).
  Splitting by output category forces every agent to read every source, worsens cross-agent
  dedup (the same event is AI *and* robotics *and* business), and creates endless boundary
  disputes. Source-modality splits align with how data is actually fetched and parsed.
- **Structured sources (RSS, GitHub releases, EDGAR) need no LLM** for the fetch step — a
  real cost saving. Only newsletter prose needs an extracting agent.
- **One shared Triage context** dedupes better than any number of coordinating agents.
- **A dedicated research-paper agent was considered and rejected** — high volume, and the
  trusted newsletters already do that triage well.

---

## 8. Provenance & trust model

The wiki must be reliable, and every statement in a tracked note must be traceable to its
source.

- **Source notes** are created at ingestion, one per item, immutable, archived
  (web.archive.org + local snapshot in `sources/_snapshots/`). Corrections / retractions →
  a new source note plus `superseded_by:` on the old one.
- **Every timeline bullet cites** one or more `[[sources/...]]`. Frontmatter values must
  each trace to a cited timeline entry (lint cross-checks).
- **Source tiers:** `primary` (filing, press release, official blog), `secondary`
  (reputable journalism), `tertiary` (newsletter summary, aggregator, speculation).
- **Claim status** when not clean: `confirmed` (default) · `reported` · `rumored` ·
  `disputed`. A material claim resting on a single tertiary source is written `rumored` and
  flagged for review.
- **Conflicts** are recorded with attribution, never silently resolved.
- **Concept notes** carry a `## Sources` section but are not ledgered fact-by-fact.
- **Viewing sources in Obsidian:** hover-preview the `[[sources/...]]` link to see the
  extract; the backlinks pane on a source note shows every claim resting on it; audit
  dashboards in `dashboards/` list rumored / disputed / single-source / dead-archive claims.
- Git provides the third leg: which agent run added a claim, and when. Source note = where
  it came from. Ledger = what was claimed. Together = a full chain from any statement back
  to its origin.

**Research papers** are deliberately *not* ingested directly — too high-volume, and the
trusted newsletters already do that triage. Deep dives are pull-on-demand: when a thread
heats up, backfill key references into its `## Key links` section.

---

## 9. Timeline growth / log rotation

Immutable ≠ one file forever. Realistic volume is manageable (a typical company runs ~50
entries over 5 years ≈ 3k words), but hot entities and the enrich agent's per-run context
cost still need bounding.

- Enrich tags each bullet `milestone` or `routine`.
- Gardener rotates: `routine` entries older than ~18–24 months move to
  `companies/_timeline/<slug>-archive.md`, leaving a `→ [[<slug>-archive]]` pointer.
  `milestone` entries and everything recent stay in the main note. Citations survive the
  move (they are links).
- `## Key milestones` (curated, gardener-maintained) at the top is the read path; the full
  timeline is the audit trail consulted occasionally.
- Year subheadings (`### 2026`) for folding.

Net: the main note stays roughly bounded regardless of how long an entity is tracked,
agent context cost stays flat, and nothing is ever actually lost.

---

## 10. Obsidian setup

Obsidian is a **read/browse surface** for the owner. Writing is done by Claude Code and the
pipeline agents (plain markdown, direct to file); the owner pushes manually.

One community plugin: **Dataview** — the dashboards and the threads' "Key entities" blocks
are Dataview queries. Nothing else is required.

- **Templater** is not used — `templates/` are static skeletons that Claude/agents copy;
  manual note creation is "duplicate the file".
- **Obsidian Git** is not used — the owner runs git directly. (Revisit only if mobile
  editing against the repo ever becomes a need.)

Vault = repo. Commit `.obsidian/` (config only; plugin code is not vendored — install
Dataview from the community store on each machine).

---

## 11. Open decisions

- **How sources physically reach the collectors.** Leading option: a dedicated Gmail for
  email-only newsletters + a self-hosted or hosted RSS aggregator (Miniflux or Feedbin) with
  an API for everything with a feed + the cloud agent fetching a few known URLs directly.
  Not yet chosen. **This blocks scaffolding the collectors.**
- Cloud-routine vs local-schedule for the eventual production cadence (prototype locally
  regardless).
- Whether paid DB APIs (Crunchbase / PitchBook) are worth it — defer until deal-sourcing
  volume justifies the cost.
- The exact starter set of concepts, threads, and seed companies.

---

## 12. Build order

1. Scaffold the vault: folders, `templates/`, `meta/schema.md`, `meta/taxonomy.md`,
   `meta/agent-instructions.md`, `meta/sources.md`, starter dashboards, README, `.obsidian/`.
2. Seed by hand: a starter set of concept notes (MCP, inference layer, RAG, agents,
   context engineering, quantization, …), ~20–40 companies, and core threads. This also
   validates the schemas.
3. Write and locally test the `lint` script.
4. Write + prototype the Triage and Enrich prompts against a handful of manually-pasted
   captures.
5. Resolve the source-delivery decision; build collectors one at a time (RSS first).
6. Add Gardener, then Digest.
7. Write `CLAUDE.md` — a lean stub: a pointer to this file plus the hard operating rules
   (append-only timelines, cite every fact, curated blocks off-limits, additive-auto /
   destructive-propose, "≥2 mentions" for new notes). Deliberately **not** created during
   scaffolding — those rules are for the operating phase and would interfere with
   owner-directed build work.
8. Migrate the stable pipeline to cloud routines + a GitHub remote.

---

## 13. Source shortlist

Kept in full in `meta/sources.md`. Starting points:

- **AI:** Import AI, The Batch, Interconnects (Nathan Lambert), AI News (smol.ai),
  Ben's Bites, Stratechery, The Information; HF Papers weekly top (aggregated feed).
- **Robotics:** The Robot Report, IEEE Spectrum Robotics, The Humanoid Hub.
- **Compute / hardware:** SemiAnalysis, The Next Platform, Chips and Cheese.
- **Startups / funding:** Crunchbase Daily, Dealroom, Sifted, TechCrunch (funding),
  CB Insights, YC directory, **SEC EDGAR Form D**, layoffs.fyi.

Prefer RSS + official APIs + forwarded email over scraping; respect ToS.
