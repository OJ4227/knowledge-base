# Handover — knowledge base build

Working notes for picking this up in a fresh session. Delete or trim once you're caught up.
**The design record is [`DESIGN.md`](DESIGN.md)** — read it first; this file is only "where we
are and what's next".

_Last updated: 2026-10-16._

---

## Repo state

- Branch `main` tracks `origin/main`. **5 local commits not yet pushed** as of this update
  (`21ba938`..`89a3bd2` — Readwise collector deny-permission, `type: capture` schema, the
  collector itself, source-register update, first live collector run). Push these before
  doing anything else if they aren't already on `origin/main`.
- Project-level Claude Code instructions and hooks provide shared context across machines
  and accounts. See `CLAUDE.md` and `.claude/settings.json`.
- `.venv/` and `meta/health/*.md` are git-ignored; recreate the venv with the commands below.
- **This repo lives in a OneDrive-synced folder.** OneDrive has been observed restoring
  files shortly after they were deleted (a sync-cache race), which reappeared as untracked
  files in `git status` after cleanup. If you delete generated files and see them come back
  untracked, check `git status` again before assuming something is wrong — it may just be
  OneDrive re-syncing a stale copy. Delete again; it hasn't recurred after a second pass.

## Where we are

Build order is in `DESIGN.md` §12. Status:

| Step | State |
|---|---|
| 1. Scaffold vault | ✅ done |
| 2. Seed by hand (concepts, ~20–40 companies, threads) | 🚧 **vertical slice only** — validated in Obsidian; needs scaling up |
| 3. `tools/lint.py` + tests | ✅ done — 47 tests pass (38 lint + 9 `collect_readwise`), 0 errors on the vault |
| 4. Prototype Triage + Enrich prompts | 🚧 **Triage built and eval-scaffolded; Enrich not started** — see below |
| 5. Resolve source-delivery decision; build collectors | 🚧 **`collect-readwise` built, tested, run against the live account** (38 sources written). `collect-tavily` and `collect-youtube` not started. |
| 6. Daily digest (watchlist alerts), then Gardener, then weekly Digest | ⬜ |
| 7. Write lean `CLAUDE.md` | ✅ done early for cross-session continuity |
| 8. Migrate to cloud routines (GitHub remote already exists) | ⬜ |

## Cross-session context

- `HANDOVER.md` records implementation progress and next actions.
- `meta/ongoing-discussions.md` records unresolved reasoning.
- `DESIGN.md` records accepted durable decisions.
- A `SessionStart` hook injects the handover, ongoing discussions, and Git state.
- A `Stop` hook checks that material discussion or implementation progress was recorded.
- Edits to the three context documents are committed and pushed automatically by the repo's
  sync hook. The sync hook does not stage unrelated files, pull, force-push, or resolve
  conflicts — ordinary content and code (like everything in this session's work) go through
  the normal Git workflow and need an explicit commit/push.

## The vertical slice (step 2 so far)

11 hand-authored notes, fully cross-linked, validated in Obsidian (graph, backlinks,
hover-preview, all dashboards):

- **Concepts:** `Model Context Protocol`, `Function calling`, `Retrieval-augmented generation`, `Model routing`
- **Companies:** `Anthropic`, `Figure AI`, `Anysphere` (all `seed: true`)
- **People:** `Brett Adcock`
- **Threads:** `Agent reliability`, `Humanoid manipulation`
- **Source:** `sources/2024-11-25-anthropic-mcp-announcement.md` (deliberately no `archive_url` yet)

Real concept↔concept link: MCP ↔ Function calling. `RAG` and `Model routing` have
`related: []` **on purpose** (control cases). Figure / Adcock / Humanoid-manipulation form a
separate graph cluster from the AI-agents cluster — **correct**, not a bug; don't force a
connecting link.

## Durable decisions (recorded in `DESIGN.md` — don't re-litigate)

- **Cross-device Claude context lives in the repository.** Maintain concise working state
  and unresolved reasoning instead of copying raw session transcripts.
- **Context synchronization is narrowly scoped.** Only `DESIGN.md`, `HANDOVER.md`, and
  `meta/ongoing-discussions.md` are automatically committed and pushed after Claude edits
  them. Ordinary content and code retain the existing Git workflow.
- **Obsidian plugins → Dataview only.** Templater dropped (templates are static skeletons —
  plain `<note name>` / `YYYY-MM-DD`, no `<% %>`). Obsidian Git dropped (owner pushes
  manually; Obsidian is a read surface). Plugin code **not vendored** — install Dataview
  from the store per machine.
- **`seed: true`** frontmatter flag = created by hand pre-pipeline; facts may be uncited,
  timeline thin; exempt from orphan / uncited-timeline / volatile-field checks.
- **Orphans** are a weak signal; concepts and `seed:` notes are excluded. Never add a
  link/note just to clear orphan status.
- **`archive_url`** on sources is expected-but-not-blocking (`missing-archive` warning) —
  web.archive.org submission isn't implemented yet (needs separate S3-style archive.org
  credentials; deferred, see `collect-readwise` below).
- **Broken links:** only broken `[[sources/...]]` citations are hard errors; any other
  unresolved `[[link]]` is a warning (usually a deliberate marker).
- **Dataview:** `FROM` excludes `templates/` and `meta/`; `GROUP BY` queries use `key` for
  the grouped value; "By category" style tables are pure summaries, names go in a flat
  "All …" table.
- Generated health reports (`meta/health/{lint-report,report}.md`) are **git-ignored**.
- **Source delivery: Readwise Reader + Tavily + YouTube transcripts** (see `DESIGN.md` §7).
  Twitter/X and Reddit are excluded from direct Stage 1 collection permanently, except via a
  curated Readwise List subscription (Readwise's infrastructure does the fetch, not a
  self-run scraper/API client).
- **`type: capture`** registered for `inbox/` raw captures (`meta/schema.md`,
  `tools/lint.py` `LOOSE_TYPES`) — loose type, structural checks only, no required fields
  beyond `type`.
- **Daily digest added as a new pipeline stage** (`DESIGN.md` §7 Stage 4, between Enrich and
  Gardener) — `digests/YYYY-MM-DD.md`, same-day summary of Enrich's output. Its
  `## Watchlist alerts` section is also the watchlist-alert mechanism: the existing
  `watchlist: true` company field (already live on all 3 seed companies, already driving
  `Deal flow` / `Stale watchlist`) now also surfaces any company that got a new `##
  Timeline` entry that day — `#milestone` and `#routine` both, no filtering. No separate
  notification channel (no email/Slack); the digest file in the repo *is* the alert. Weekly
  Digest (now Stage 6) and Gardener (now Stage 5) are unchanged in shape, just renumbered.
  Not yet built — needs the Triage/Enrich prompts (step 4) first, since it only summarizes
  what Enrich wrote that day.

## `tools/lint.py`

```bash
# recreate the env (git-ignored)
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-dev.txt

.venv/bin/python tools/lint.py            # lint whole vault; writes meta/health/lint-report.md
.venv/bin/python tools/lint.py --strict   # warnings also fail
.venv/bin/pytest tools/                   # 47 tests
```

Current vault: **0 errors, 57 warnings** (all expected — `[[Competitor]]` / `[[future
concept]]` markers, the one seed source's missing archive, and `missing-archive` on every
collected source, plus a handful of `stub` warnings on short-content captures).

Not yet implemented (need git-diff or network): curated-block tamper detection, dead
external-link checking. Add with the pipeline.

## `tools/collect_readwise.py` — built, tested, run against the live account

The first working Stage 1 collector. Full usage in `tools/README.md`. Summary:

- Pulls documents from `GET https://readwise.io/api/v3/list/` updated since the last run
  (`updatedAfter`, paginated via `nextPageCursor`), using `withHtmlContent=true` for content
  (there is **no** `withFullContent` parameter — an earlier design-doc assumption was wrong
  and has been corrected in `DESIGN.md` §7 after checking the live API docs).
- For each new top-level document (highlights/notes with `parent_id` set are filtered out):
  writes a `sources/<slug>.md` note, a `sources/_snapshots/<slug>.html` local snapshot (the
  raw `html_content` — this is the "local copy," no web.archive.org submission yet), and an
  `inbox/<slug>--capture.md` raw capture (`type: capture`, excerpt + `[[sources/...]]` link).
  The `--capture` suffix keeps the inbox filename's stem distinct from the source note's —
  sharing a stem is a lint `duplicate-name` error (ambiguous `[[wikilink]]` resolution).
- Idempotent: dedupes by Readwise document `id`, stored as an HTML comment
  (`<!-- readwise_id: ... -->`) at the top of each source note. A second run with no new
  Readwise activity writes nothing.
- **Watermark** lives in `meta/collector-state.json` (`{"readwise": {"last_run_utc": ...}}`)
  and is **committed to the repo, not git-ignored** — deliberate. `collect-readwise` is a
  batch job, not a long-running service; it doesn't need a laptop left on. Running it
  manually/via cron locally now is fine for prototyping (a skipped run just means a wider
  `updatedAfter` window next time). Committing the watermark means moving to an always-on
  runner later (GitHub Actions or the "Claude cloud routines" `DESIGN.md` names) needs no
  state migration — a `git pull` picks up exactly where the last run left off. See
  `meta/ongoing-discussions.md` → "Production scheduling / collector hosting".
- **First real run (2026-10-13):** 38 sources/captures/snapshots written, 0 lint errors.
  Includes expected noise the collector deliberately does **not** filter: a few cross-posted
  duplicates (the same newsletter issue arriving via both RSS and email as two separate
  Readwise document IDs — e.g. "TLDR - Confirm your signup") and 3 of Readwise's own
  onboarding articles (not from any tracked feed). Per `meta/agent-instructions.md`, dropping
  noise and deduping across sources is Stage 2 (Triage)'s job, not the collector's — this is
  exactly the kind of cross-source dedup problem `DESIGN.md` §7 designed Triage to solve, and
  it's sitting there in `inbox/` right now as a real test case.
- Re-run immediately after confirmed idempotent (0 new documents, watermark unchanged).

Config: `tools/.env` (git-ignored, Read-denied for Claude in `.claude/settings.json` — see
`tools/.env.example` for the convention). Requires `READWISE_TOKEN`
(`https://readwise.io/access_token`).

## Other collectors — not built yet

- **`collect-tavily`** — Tavily news-search API, free tier (1,000 credits/month). Connectivity
  confirmed via a manual test this session (`topic=news`, date-bounded search returned real,
  current funding stories). The query list (which threads/domains get a daily date-bounded
  search) is intentionally undecided — see `meta/ongoing-discussions.md`.
- **`collect-youtube`** — owner wants `youtube-transcript-api` (free, open-source, no API
  key) added as a planned source. Not yet added to `meta/sources.md` / `DESIGN.md` §7, and no
  script written.
- **Twitter/X via Readwise List** — the owner's List has no members yet; checked live via
  the API this session (`category=tweet` and `location=feed` both returned zero X-sourced
  items). `collect_readwise.py` will pick this content up automatically once populated — the
  List delivers through the same `GET /list/` endpoint, no separate code path needed. Nothing
  to verify yet.

## Open decisions

See `meta/ongoing-discussions.md` for the live reasoning, status, and next question for
each unresolved design topic.

## Recommended next step

**(b) Triage + Enrich prompts (step 4) — start here.** There are 38 real, unprocessed
captures sitting in `inbox/` right now from the first `collect-readwise` run. Write and
dry-run the Triage prompt against them: it should classify each on the taxonomy
(`meta/taxonomy.md`), dedupe the known cross-posted pairs (e.g. the two "TLDR" items, the
three "Meta Wonder..." items), and drop the 3 Readwise onboarding articles as noise. This
is a much better test than hand-pasted fixtures — the design was explicitly built to need
real messy data for Triage to prove itself against, and now it exists.

Other options, lower priority:

- **(a) Bulk-seed (finish step 2)** — ~10–15 more evergreen concepts, ~20–40 companies,
  ~6–10 threads. Large review load; draft in batches into a scratch file for review before
  writing to the vault.
- **(c) Build `collect-tavily`** — needs a query list decided first (see
  `meta/ongoing-discussions.md`), then follow `collect_readwise.py`'s pattern (same
  `meta/collector-state.json`, same `type: capture` inbox output).
- **(d) Add `collect-youtube`** — needs a starter channel/video list first.

## Working style (carried across sessions)

- Owner reviews content closely and wants push-back on suboptimal choices *before*
  execution — see `~/.claude/CLAUDE.md`. Raise once, then proceed if overruled.
- File-by-file `Write` review was slow for bulk content. Prefer **drafting a batch into a
  scratch `.md`, sending for review, then writing all at once.**
- Owner sometimes reviews on mobile — offer to print long files in chat or use
  `SendUserFile`.
- Keep commit messages short. Separate unrelated changes into separate commits (this
  session's collector work was split into 5: permissions, schema change, the script itself,
  source-register update, and the generated run output — each independently reviewable).
- Before deleting generated/untracked files, confirm with the owner first even when Git
  history shows nothing would be lost — see Git Safety Protocol in `~/.claude/CLAUDE.md`.
- When testing anything that needs a secret (API token), never have Claude read the secret
  file directly — the owner pastes/edits it themselves, Claude only runs commands that
  reference it via environment variable.
