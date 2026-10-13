# Handover — knowledge base build

Working notes for picking this up in a fresh session. Delete or trim once you're caught up.
**The design record is [`DESIGN.md`](DESIGN.md)** — read it first; this file is only "where we
are and what's next".

_Last updated: 2026-10-13._

---

## Repo state

- Branch `main` tracks `origin/main`.
- Latest baseline commit before the cross-session context work:
  `6b378c7 Harden vault linter and add pre-commit gate`.
- Project-level Claude Code instructions and hooks now provide shared context across
  machines and accounts. See `CLAUDE.md` and `.claude/settings.json`.
- `.venv/` and `meta/health/*.md` are git-ignored; recreate the venv with the commands below.

## Where we are

Build order is in `DESIGN.md` §12. Status:

| Step | State |
|---|---|
| 1. Scaffold vault | ✅ done |
| 2. Seed by hand (concepts, ~20–40 companies, threads) | 🚧 **vertical slice only** — validated in Obsidian; needs scaling up |
| 3. `tools/lint.py` + tests | ✅ done — 38 tests pass, 0 errors on the vault |
| 4. Prototype Triage + Enrich prompts | ⬜ not started |
| 5. Resolve source-delivery decision; build collectors | 🚧 **`collect-readwise` built, tested, and run against the live Readwise account** (38 sources + captures written, idempotency verified). `collect-tavily` and `collect-youtube` not started. |
| 6. Gardener, then Digest | ⬜ |
| 7. Write lean `CLAUDE.md` | ✅ done early for cross-session continuity |
| 8. Migrate to cloud routines (GitHub remote already exists) | ⬜ |

## Cross-session context

- `HANDOVER.md` records implementation progress and next actions.
- `meta/ongoing-discussions.md` records unresolved reasoning.
- `DESIGN.md` records accepted durable decisions.
- A `SessionStart` hook injects the handover, ongoing discussions, and Git state.
- A `Stop` hook checks that material discussion or implementation progress was recorded.
- Edits to the three context documents are committed and pushed automatically. The sync
  hook does not stage unrelated files, pull, force-push, or resolve conflicts.

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

- **Cross-device Claude context lives in the repository.** Maintain concise working state
  and unresolved reasoning instead of copying raw session transcripts.
- **Context synchronization is narrowly scoped.** Only `DESIGN.md`, `HANDOVER.md`, and
  `meta/ongoing-discussions.md` are automatically committed and pushed after Claude edits
  them. Ordinary content and code retain the existing Git workflow.
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
.venv/bin/pytest tools/                   # 47 tests (38 lint + 9 collect_readwise)
```

Current vault: **0 errors, 57 warnings** (all expected — `[[Competitor]]` / `[[future
concept]]` markers, the seed source's missing archive, and `missing-archive` on every
collected source — see below).

Not yet implemented (need git-diff or network): curated-block tamper detection, dead
external-link checking. Add with the pipeline.

## Source-delivery decision and `collect-readwise` (this session)

Collector tooling decided and the first collector built — see `DESIGN.md` §7 and
`meta/sources.md`:

- **`collect-readwise`** (`tools/collect_readwise.py`) — **built, tested, run against the
  live Readwise account.** A paid Readwise Reader subscription (owner is paying). Newsletters
  subscribe directly to the account's `@feed.readwise.io` address; RSS feeds go in the same
  Reader inbox. The script pulls documents updated since the last run
  (`GET /api/v3/list/`, `updatedAfter`, paginated via `nextPageCursor`), using
  `withHtmlContent=true` (not `withFullContent` — that parameter doesn't exist; corrected in
  `DESIGN.md` §7 after a research pass against the live API docs). Writes a `sources/` note
  + local HTML snapshot + `inbox/` capture per new top-level document (highlights/notes with
  `parent_id` set are filtered out). Replaces the earlier dedicated-Gmail + Miniflux/Feedbin
  plan.
  - **Watermark** (`meta/collector-state.json`, `{"readwise": {"last_run_utc": ...}}`) is
    **committed to the repo**, not git-ignored — deliberate, so whichever machine or CI
    runner executes the collector next (GitHub Actions / Claude cloud routines, per
    `DESIGN.md` §12 step 8) picks up exactly where the last run left off. See
    `meta/ongoing-discussions.md` → "Collector hosting" for the still-open question of
    where this actually runs day to day.
  - **First real run:** 38 sources written (0 lint errors; `missing-archive` warnings only,
    expected — no web.archive.org submission in this version, deferred per the plan since it
    needs separate S3-style archive.org credentials). Re-run confirmed idempotent (0 new
    documents, watermark unchanged).
  - **New note type:** `type: capture` registered in `meta/schema.md` and `tools/lint.py`'s
    `LOOSE_TYPES` for `inbox/` files (structural checks only, no required fields).
  - Two bugs caught and fixed during the first live run: inbox files need `type: capture`
    frontmatter (lint requires it on every file), and inbox/source filenames must not share
    a stem (`<slug>--capture.md` vs `<slug>.md` — avoids wikilink ambiguity).
- **`collect-tavily`** — Tavily news-search API, free tier (1,000 credits/month), confirmed
  working via manual test (`topic=news`, date-bounded). Not yet built as a script; query
  list intentionally paused (see `meta/ongoing-discussions.md`).
- **`collect-youtube`** — owner wants `youtube-transcript-api` (free, no key) added as a
  planned source in `meta/sources.md` / `DESIGN.md` §7. Not yet added or built.
- Twitter/X and Reddit are **excluded from direct Stage 1 collection permanently** (no free,
  ban-safe, incremental-fetch option for self-run infrastructure), except via a curated
  Readwise List subscription (Readwise's own infrastructure does the fetch) — tested live
  this session (`category=tweet` and `location=feed` both empty; the List has no
  members/digests yet). `collect_readwise.py` will pick this content up automatically once
  it starts flowing — no separate code path needed.

## Open decisions

See `meta/ongoing-discussions.md` for the live reasoning, status, and next question for
each unresolved design topic.

## Recommended next step

Pick one:

- **(a) Bulk-seed (finish step 2)** — ~10–15 more evergreen concepts, ~20–40 companies,
  ~6–10 threads. Large review load; draft in batches into a scratch file for review before
  writing to the vault.
- **(b) Triage + Enrich prompts (step 4)** — write and dry-run against a few hand-pasted
  captures. Tests the pipeline design early; doesn't need collector code.
- **(c) Build `collect-readwise` (step 5)** — now unblocked. Sign up for Readwise Reader,
  subscribe the AI/robotics/hardware/funding newsletters and RSS feeds from
  `meta/sources.md` to the feed address, then write the collector script against the Reader
  API.

Suggested order: (b) or (c) first — both are now unblocked and independent of each other —
then (a) once note conventions are exercised by the Enrich prompt.

## Working style (from this session)

- Owner reviews content closely and wants push-back on suboptimal choices *before*
  execution — see `~/.claude/CLAUDE.md`. Raise once, then proceed if overruled.
- File-by-file `Write` review was slow. Prefer **drafting a batch into a scratch `.md`,
  sending for review, then writing all at once.**
- Owner sometimes reviews on mobile — offer to print long files in chat or use
  `SendUserFile`.
- Keep commit messages short.
