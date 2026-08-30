---
type: meta
name: Taxonomy
updated: 2026-08-30
---

# Taxonomy

Controlled vocabularies. Triage and Enrich must use these exact values.

## Capture classification

Every capture is tagged on two axes.

### Domain

| Value | Covers |
|---|---|
| `ai` | Models, training, algorithms, AI products and applications, AI labs |
| `robotics` | Physical robots, manipulation, locomotion, sim, robot learning, robotics companies |
| `hardware/compute` | Chips, accelerators, interconnect, data centres, memory, power |
| `business` | Funding, M&A, hiring, org changes, strategy, market moves, shutdowns |

A capture may carry more than one domain (a humanoid-robotics raise is `robotics` +
`business`).

### Development type

| Value | Definition | Example |
|---|---|---|
| `model-release` | New model / version / weights / API | "Anthropic releases Claude 4.5" |
| `research` | Notable paper, technique, result (incl. negative) | "New attention variant cuts KV cache 4x" |
| `capability-demo` | Demonstrated capability, not necessarily shipped | "Robot folds laundry autonomously" |
| `product` | Shipped product / feature / developer tool | "OpenAI ships hosted agents" |
| `hardware` | Chip, sensor, actuator, robot platform | "NVIDIA announces GB300" |
| `benchmark` | New eval, leaderboard move, saturation | "SWE-bench Verified passes 80%" |
| `open-source` | Significant repo / dataset / tooling release | "Meta open-sources a world model" |
| `funding` | Priced round, grant, large debt | "Figure raises $1.5B Series C" |
| `m&a` | Acquisition, merger, acquihire | "OpenAI acquires io" |
| `people-move` | Notable hire, departure, founding | "Chief scientist leaves to found startup" |
| `shutdown` | Wind-down, mass layoffs, pivot away | "Robotics startup shuts down" |
| `policy` | Regulation, standards, export controls | "New EU rules on frontier models" |

## Company sectors (`sectors:` field)

Non-exhaustive; extend as needed but keep it small and reuse existing values.

`foundation-models` · `ai-applications` · `ai-infra` · `ai-tooling` · `ai-agents` ·
`humanoid` · `industrial-robotics` · `mobile-robotics` · `robot-learning` · `autonomy` ·
`semiconductors` · `ai-hardware` · `data-center` · `edge-compute` · `simulation`

## Starter threads (`topics/`, `kind: thread`)

Seed these in build step 2; add more as narratives emerge.

- Humanoid manipulation
- Test-time compute / reasoning models
- Long-context & memory
- On-device / edge models
- Agent reliability
- Custom silicon vs NVIDIA
- Inference cost curves
- World models for robotics
- Open vs closed frontier models

## Source tiers (`tier:` field)

| Tier | Meaning |
|---|---|
| `primary` | First-party: SEC filing, company press release, official blog, spec, paper by the authors |
| `secondary` | Reputable independent journalism with editorial standards |
| `tertiary` | Newsletter summary, aggregator, analyst note, social post, rumour |

## Claim status

`confirmed` (default) · `reported` · `rumored` · `disputed`. A material claim resting only
on a single `tertiary` source is written `rumored` and flagged for review.
