---
type: meta
name: Source register
updated: 2026-08-30
---

# Source register

The canonical list of feeds the collectors pull. `status`: `planned` until wired up,
`active` once a collector is ingesting it, `dropped` if removed (keep the row, note why).

Delivery: `rss` · `email` (dedicated Gmail) · `api` · `scrape` (avoid; only if no
alternative and ToS permits).

## AI

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| Import AI (Jack Clark) | tertiary | rss / email | planned | Weekly; policy + research + industry |
| The Batch (DeepLearning.AI) | tertiary | rss / email | planned | Weekly digest |
| Interconnects (Nathan Lambert) | secondary | rss / email | planned | Post-training, open models |
| AI News (smol.ai) | tertiary | rss / email | planned | High-volume daily; strong for releases |
| Ben's Bites | tertiary | email | planned | Daily, product-focused |
| Stratechery / Sharp Tech | secondary | rss / email | planned | Strategy, paywalled |
| The Information | secondary | email | planned | Paywalled; strong AI/robotics scoops |
| Hugging Face Papers (weekly top) | secondary | rss | planned | Pre-ranked; the only research feed |

## Robotics

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| The Robot Report | secondary | rss | planned | Industry + funding |
| IEEE Spectrum Robotics | secondary | rss | planned | Technical journalism |
| The Humanoid Hub | tertiary | rss / email | planned | Humanoid-specific tracking |

## Compute / hardware

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| SemiAnalysis | secondary | rss / email | planned | Data centre, accelerators; partly paywalled |
| The Next Platform | secondary | rss | planned | HPC / data centre |
| Chips and Cheese | secondary | rss | planned | Microarchitecture deep dives |

## Startups / funding

| Source | Tier | Delivery | Status | Notes |
|---|---|---|---|---|
| Crunchbase Daily | tertiary | email | planned | Free digest; API is paid |
| Dealroom | secondary | api / email | planned | Europe-strong |
| Sifted | secondary | rss / email | planned | European startups |
| TechCrunch (funding tag) | secondary | rss | planned | `techcrunch.com/tag/funding/feed/` |
| CB Insights | tertiary | email | planned | Newsletter |
| Y Combinator company directory | primary | api / scrape | planned | New-batch signal; check ToS |
| SEC EDGAR Form D | primary | api | planned | Free; earliest US raise signal |
| layoffs.fyi | tertiary | scrape | planned | Shutdown / layoff signal |

## Delivery infrastructure — TBD (DESIGN.md §11)

Leading plan: dedicated Gmail for `email` sources + a self-hosted Miniflux (or hosted
Feedbin) instance with an API for all `rss` sources + collectors calling `api` sources
directly. Not yet decided; blocks Stage 1.
