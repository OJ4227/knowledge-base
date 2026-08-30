# AI / Robotics / Startups Knowledge Base

An Obsidian "AI wiki" covering developments in AI, robotics, and the startups and growing
companies in those industries. Populated largely by automated agents from trusted sources,
plus hand-curated reference material.

## Start here

**[`DESIGN.md`](DESIGN.md)** is the design record and single source of truth — purpose,
structure, note schemas, the agent pipeline, provenance model, and build order. Read it in
full before working on the vault's architecture, agents, or tooling.

There is intentionally **no `CLAUDE.md` yet** — it is added at the end of the build
(`DESIGN.md` §12 step 7) so its operating rules don't interfere with scaffolding.

## Structure

| Folder | Contents |
|---|---|
| `concepts/` | Evergreen explainers — how modern AI/LLM systems work (MCP, inference layers, RAG, …). Stable, curated. |
| `companies/` | One note per tracked company. `_timeline/` holds rotated timeline archives. |
| `people/` | Founders, key operators, notable researchers. |
| `technologies/` | Specific tracked artefacts with a lifecycle — models, hardware, robots, frameworks, benchmarks. |
| `topics/` | Maps of Content and "threads" — long-running narratives that accumulate developments. |
| `inbox/` | Agent drop zone: unprocessed raw captures. |
| `sources/` | One note per source item (provenance). `_snapshots/` holds archived copies. |
| `digests/` | Weekly "what changed" summaries. |
| `dashboards/` | Dataview queries. |
| `templates/` | Note templates (Templater). |
| `meta/` | `schema.md`, `taxonomy.md`, `agent-instructions.md`, `sources.md`, `rejected-links.md`, `health/`, `review/`. |

## Obsidian setup

This vault **is** the git repo. Open the folder directly as an Obsidian vault.

Required community plugins (install from Obsidian settings — they are not vendored here):

- **Dataview** — dashboards and embedded queries
- **Templater** — note templates in `templates/`
- **Obsidian Git** — pull agent commits, optionally push

After installing, point Templater's template folder at `templates/`.

## Status

Design agreed; vault scaffolded (`DESIGN.md` §12 step 1 complete). Not yet seeded with
content, and the agent pipeline is not built. Next: seed concept notes, companies, and
threads by hand (step 2).
