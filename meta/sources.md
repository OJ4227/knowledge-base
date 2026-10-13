---
type: meta
name: Source register
updated: 2026-10-09
---

# Source register

The canonical list of feeds the collectors pull. `status`: `planned` until wired up,
`active` once a collector is ingesting it, `dropped` if removed (keep the row, note why).

Delivery: `readwise` (RSS feeds and email newsletters, both via the Readwise Reader
subscription — see below) · `tavily` (date-bounded news search) · `youtube` (transcript
pull) · `api` (direct, e.g. SEC EDGAR) · `scrape` (avoid; only if no alternative and ToS
permits).

## AI

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| Import AI (Jack Clark) | tertiary | readwise | planned | Weekly; policy + research + industry |
| The Batch (DeepLearning.AI) | tertiary | readwise | planned | Weekly digest |
| Interconnects (Nathan Lambert) | secondary | readwise | planned | Post-training, open models |
| AI News (smol.ai) | tertiary | readwise | planned | High-volume daily; strong for releases |
| Ben's Bites | tertiary | readwise | planned | Daily, product-focused |
| Stratechery / Sharp Tech | secondary | readwise | planned | Strategy, paywalled |
| The Information | secondary | readwise | planned | Paywalled; strong AI/robotics scoops |
| Hugging Face Papers (weekly top) | secondary | readwise | planned | Pre-ranked; the only research feed |

## Robotics

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| The Robot Report | secondary | readwise | planned | Industry + funding |
| IEEE Spectrum Robotics | secondary | readwise | planned | Technical journalism |
| The Humanoid Hub | tertiary | readwise | planned | Humanoid-specific tracking |

## Compute / hardware

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| SemiAnalysis | secondary | readwise | planned | Data centre, accelerators; partly paywalled |
| The Next Platform | secondary | readwise | planned | HPC / data centre |
| Chips and Cheese | secondary | readwise | planned | Microarchitecture deep dives |

## Startups / funding

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| Crunchbase Daily | tertiary | readwise | planned | Free digest; API is paid |
| Dealroom | secondary | api / readwise | planned | Europe-strong |
| Sifted | secondary | readwise | planned | European startups |
| TechCrunch (funding tag) | secondary | readwise | planned | `techcrunch.com/tag/funding/feed/` |
| CB Insights | tertiary | readwise | planned | Newsletter |
| Y Combinator company directory | primary | api / scrape | planned | New-batch signal; check ToS |
| SEC EDGAR Form D | primary | api | planned | Free; earliest US raise signal |
| layoffs.fyi | tertiary | scrape | planned | Shutdown / layoff signal |

## Delivery infrastructure (DESIGN.md §7)

Decided: a paid Readwise Reader subscription handles every `readwise`-delivery row above —
newsletters subscribe directly to the account's `@feed.readwise.io` address, RSS feeds are
added in the same Reader inbox. One `collect-readwise` script pulls new documents daily via
the Reader API. `api`-delivery rows (SEC EDGAR) are fetched directly; `scrape` rows are
last-resort only, per the delivery legend above. Tavily (news search) and a YouTube
transcript puller cover topics/content with no newsletter or feed — see `DESIGN.md` §7 for
both.
