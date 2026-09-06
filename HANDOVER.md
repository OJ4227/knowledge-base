# Handover — knowledge base build

Working notes for picking this up in a fresh session. Delete or trim once you're caught up.
**The design record is [`DESIGN.md`](DESIGN.md)** — read it first; this file is only "where we
are and what's next".

_Last updated: 2026-09-06._

---

## Repo state

- Branch `main`, in sync with `origin/main` (pushed). Commits:
  - `5f22616` Initial commit
  - `d44ec7b` Vertical slice notes
  - `be5083e` Vault linter + pytest fixtures
- Working tree clean. `HANDOVER.md` itself is untracked — commit it if you want it to travel.
- `.venv/` and `meta/health/*.md` are git-ignored; recreate the venv with the commands below.

## Where we are

Build order is in `DESIGN.md` §12. Status:

| Step | State |
|---|---|
| 1. Scaffold vault | ✅ done |
| 2. Seed by hand (concepts, ~20–40 companies, threads) | 🚧 **vertical slice only** — validated in Obsidian; needs scaling up |
| 3. `tools/lint.py` + tests | ✅ done — 33 tests pass, 0 errors on the vault |
| 4. Prototype Triage + Enrich prompts | ⬜ not started |
| 5. Resolve source-delivery decision; build collectors | ⬜ blocked on the open decision |
| 6. Gardener, then Digest | ⬜ |
| 7. Write lean `CLAUDE.md` | ⬜ deliberately deferred to end |
| 8. Migrate to cloud routines (GitHub remote already exists) | ⬜ |

## The vertical slice (step 2 so far)

11 notes, fully cross-linked, validated in Obsidian (graph, backlinks, hover-preview,
all dashboards):

- **Concepts:** `Model Context Protocol`, `Function calling`, `Retrieval-augmented generation`, `Model routing`
- **Companies:** `Anthropic`, `Figure AI`, `Anysphere` (all `seed: true`)
- **People:** `Brett Adcock`
- **Threads:** `Agent reliability`, `Humanoid manipulation`
- **Source:** `sources/2024-11-25-anthropic-mcp-announcement.md` (deliberately no `archive_url` yet)

Real concept↔concept link: MCP ↔ Function calling. `RAG` and `Model routing` have
`related: []` **on purpose** (control cases). Figure / Adcock / Humanoid-manipulation form a
separate graph cluster from the AI-agents cluster — **correct**, not a bug; don't force a
connecting link.

## Decisions this session (DESIGN.md already updated to match — don't re-litigate)

- **Obsidian plugins → Dataview only.** Templater dropped (templates are static skeletons
  now — plain `<note name>` / `YYYY-MM-DD`, no `<% %>`). Obsidian Git dropped (owner pushes
  manually; Obsidian is a read surface). Plugin code **not vendored** — install Dataview
  from the store per machine.
- **`seed: true`** frontmatter flag = created by hand pre-pipeline; facts may be uncited,
  timeline thin; exempt from orphan / uncited-timeline / volatile-field checks.
- **Orphans** are a weak signal; concepts and `seed:` notes are excluded. Never add a
  link/note just to clear orphan status.
- **`archive_url`** on sources is expected-but-not-blocking (`missing-archive` warning) —
  collectors that archive don't exist yet.
- **Broken links:** only broken `[[sources/...]]` citations are hard errors; any other
  unresolved `[[link]]` is a warning (usually a deliberate marker).
- **Dataview:** `FROM` excludes `templates/` and `meta/`; `GROUP BY` queries use `key` for
  the grouped value; "By category" style tables are pure summaries, names go in a flat
  "All …" table.
- Generated health reports (`meta/health/{lint-report,report}.md`) are **git-ignored**.

## `tools/lint.py`

```bash
# recreate the env (git-ignored)
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-dev.txt

.venv/bin/python tools/lint.py            # lint whole vault; writes meta/health/lint-report.md
.venv/bin/python tools/lint.py --strict   # warnings also fail
.venv/bin/pytest tools/                   # 33 tests
```

Current vault: **0 errors, 15 warnings** (all expected — `[[Competitor]]` / `[[future
concept]]` markers + the seed source's missing archive).

Not yet implemented (need git-diff or network): curated-block tamper detection, dead
external-link checking. Add with the pipeline.

## Open decisions (DESIGN.md §11)

1. **How sources physically reach the collectors** — dedicated Gmail + RSS aggregator
   (Miniflux/Feedbin) API + direct URL fetches is the leading option. **Blocks step 5.**
2. Cloud routine vs local schedule for production cadence.
3. Paid DB APIs (Crunchbase / PitchBook) — deferred until deal-sourcing volume justifies.
4. The full starter set of concepts / threads / seed companies.

## Recommended next step

Pick one:

- **(a) Bulk-seed (finish step 2)** — ~10–15 more evergreen concepts, ~20–40 companies,
  ~6–10 threads. Large review load; draft in batches into a scratch file for review before
  writing to the vault.
- **(b) Triage + Enrich prompts (step 4)** — write and dry-run against a few hand-pasted
  captures. Tests the pipeline design early; doesn't need the source-delivery decision.
- **(c) Small: git `pre-commit` hook** running `lint.py` (agent-instructions says "every
  commit"). ~15 min. Not yet done.

Suggested order: (c) now, then (b), then (a) once note conventions are also exercised by
the Enrich prompt.

## Working style (from this session)

- Owner reviews content closely and wants push-back on suboptimal choices *before*
  execution — see `~/.claude/CLAUDE.md`. Raise once, then proceed if overruled.
- File-by-file `Write` review was slow. Prefer **drafting a batch into a scratch `.md`,
  sending for review, then writing all at once.**
- Owner sometimes reviews on mobile — offer to print long files in chat or use
  `SendUserFile`.
- Keep commit messages short.
