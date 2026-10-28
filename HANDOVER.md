# Handover — knowledge base build

Working notes for picking this up in a fresh session. Delete or trim once you're caught up.
**The design record is [`DESIGN.md`](DESIGN.md)** — read it first; this file is only "where we
are and what's next".

_Last updated: 2026-10-28._

---

## Repo state

- Branch `main` tracks `origin/main` and is fully pushed (verified 2026-10-28) — nothing
  outstanding to push.
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
| 4. Prototype Triage + Enrich prompts | 🚧 **Both built. Triage run for real (88 items, hand-reviewed). Enrich built + committed, eval NOT yet run (costs money) — this is the next action, see below** |
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
- **`meta/agent-instructions.md` split into one file per stage** (2026-10-28):
  `meta/agent-instructions/{hard-rules,collectors,triage,enrich,daily-digest,gardener,
  weekly-digest,lint}.md` + a `README.md` index. The single-file version required fragile
  heading-text slicing (`text.index("### Triage...")`) that `triage.py` already did and
  `enrich.py` would have had to replicate — an edit to any heading would silently break
  extraction. The old file was deleted outright, not kept as a redirect stub; every
  cross-reference in the repo was updated to the specific new file. Any new pipeline stage
  script should read its own file directly, never the old combined path (which no longer
  exists).
- **`meta/pending-entities.md` added, committed to git (not git-ignored)** — holds full,
  cited, timeline-ready facts for entities that haven't cleared the "≥2 independent
  mentions" bar (`meta/agent-instructions/enrich.md` hard rule 5) yet. Rule 5 exists to
  avoid note *bloat*, not to discard information (`DESIGN.md` §2 says so explicitly) — so
  deferring *where* a fact lives must never mean weakening the fact. An existing unresolved
  `[[EntityName]]` link anywhere in the vault also counts as a prior mention. Unlike
  `meta/health/*.md` (generated, git-ignored), this file is the *only* copy of a
  first-mention fact until a second mention arrives, sometimes months later — losing it
  would be a real, permanent data loss, so it's committed like `meta/collector-state.json`.

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

## Triage (Stage 2) — built, evaluated, and run for real against the live inbox

Built: `tools/prompts/triage.md` (the prompt — interpolates `meta/taxonomy.md` and the
Triage section of `meta/agent-instructions.md` at runtime rather than restating them, so
it can't drift from the design), `tools/triage.py` (the runner — follows
`collect_readwise.py`'s conventions: module-level path constants, `@dataclass`,
`run()`/`main()`, `--dry-run`), and an eval harness: `tools/evals/run_eval.py` +
10 hand-labelled golden cases in `tools/evals/cases/triage/*.json`, scored against the
real 35-capture inbox corpus (noise, easy/hard/triplet dedup, newsletter fan-out, a
sponsor-block-that-is-real-news trap, an off-domain issue, two opinion contrast cases, a
new-company case, and the one capture that touches all three existing vault entities).

**Design decisions made alongside the build (see `DESIGN.md` §2/§6/§7 and
`meta/taxonomy.md`/`meta/agent-instructions.md` for the recorded versions):**
- **Fan-out, not 1:1** — a newsletter capture becomes N classified items, one per
  development, not one blob per input file.
- **Opinion is a 13th taxonomy value, not auto-dropped** — kept only when it clears a
  "non-obvious claim" bar judged on the body, never the headline; a kept opinion item
  never gets a `## Timeline` entry (added as a second exception to the ledger, alongside
  concepts) — it surfaces in the daily digest's new `## Opinion & analysis` section and,
  if durable, a thread's `## Key links`.
- **Triage output is one JSON file per run** (`inbox/_triage/YYYY-MM-DD.json`), not N
  markdown notes — `inbox/README.md` is updated to match. A merged duplicate is one item
  with multiple `sources`.
- **Model choice is deferred to measurement, not assumed.** `triage.py --model` makes the
  model a flag; `run_eval.py --model` sweeps it. Nothing has been run for real yet, so
  there is no chosen model — sweep Haiku 4.5 → Sonnet 5 → Opus 5 and take the cheapest
  that holds the eval score before committing to one.
- **Eval assertions are deterministic Python, no LLM judge** — even the two opinion cases,
  where the *judgment* (is this a non-obvious claim?) is hand-labelled by a human into the
  golden file once, and the assertion just checks the model's decision against that label.

**Verified this session (all free — no API key was used, no money spent):**
`--dry-run` prints a correctly assembled prompt; 10 new mocked plumbing tests in
`tools/tests/test_triage_script.py` pass (57/57 total with the existing suite); the eval
scorer's every check type was verified against hand-built `TriageResult` fixtures: 0 lint
errors throughout.

**Backend decision (recorded in `DESIGN.md` §2, 2026-10-22): direct API with a
structured-output schema, not the Claude Code subscription.** The subscription-via-`claude
-p` alternative was researched and explicitly deferred (not ruled out) — revisit only if
added sources push real monthly cost high enough to matter; see `DESIGN.md` §2 for the
full reasoning.

**Credential resolution (added after the initial build):** `tools/triage.py`'s
`build_client()` (reused by `run_eval.py`) checks `ANTHROPIC_BASE_URL` +
`ANTHROPIC_AUTH_TOKEN` first (a gateway/proxy in front of the API, Bearer auth — e.g. this
machine's global `~/.claude/settings.json` already sets these to route through a Deloitte
relay) and falls back to `ANTHROPIC_API_KEY` only if those aren't set — same priority
Claude Code itself uses. **This is not a Claude Pro/Max subscription OAuth token** —
subscription OAuth is scoped to the Claude Code client only and is rejected by the
Messages API outside it (enforced server-side since Jan 2026; using it elsewhere also
violates the Consumer ToS). A real API key (direct or via an authorized gateway) is
required either way.

A real bug surfaced and was fixed while wiring this up: the test fixture
(`isolated_vault` in `test_triage_script.py`) only ever cleared `ANTHROPIC_API_KEY`, so on
a machine with ambient `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` set (like this one),
4 of the "mocked" tests actually made a live network call to the real gateway before the
mock could intercept it. Fixed by clearing all three credential env vars in the fixture.
**Lesson for future credential-resolution changes in this repo: a test isolation fixture
must clear every env var a new resolution path reads, not just the one it's named after.**

**Eval baseline achieved and model chosen (2026-10-27).** Live runs through the gateway
surfaced two real bugs, now fixed (see `DESIGN.md` §2 and the git log):
`model_json_schema()` doesn't set `additionalProperties: false`, which this gateway's
Vertex backend requires (fixed with `ConfigDict(extra="forbid")` on all three schema
classes); and the SDK's default `anthropic-version` header conflicts with the gateway's
own body-level version pin (fixed by omitting the header on the gateway path only, via
`anthropic.Omit()` in `build_client()`).

Comparison run across Sonnet 5 (default + `xhigh` effort, twice) and Opus 5: Sonnet
scored 16/20 consistently regardless of effort (ruling out "needs more thinking depth");
Opus scored 20/23 at a comparable cost (~$0.38 vs. ~$0.33–0.41/run) — **`claude-opus-5` is
now `DEFAULT_MODEL` in `triage.py`**. `--model`/`--effort` remain flags on both scripts for
re-measurement later.

Along the way, 4 of the 10 golden cases turned out to have hand-labels that were too
narrow — not model errors. Each failure was checked against the actual model output
before the case was revised (see the "Revise 4 golden cases" commit for the full
reasoning per case): `dup-hard-gemini-carbon` required `m&a` where `funding` is equally
defensible; `off-domain-fintech` and `end-to-end-figure` pinned a `development_type` that
varied defensibly across runs (dropped the type constraint, kept the entity-match check);
`opinion-zuckerberg-drop` was a blanket all-dropped assertion that didn't account for
fan-out applying to opinion too — rewritten to require the one real falsifiable claim
buried in the rant (a Llama-vs-Chinese-labs prediction) survive, not a single keep/drop
verdict on the whole capture. **Lesson: when an eval case fails, read the actual model
output before assuming the model is wrong — several of these "failures" were the eval
teaching me my own hand-label was too strict.**

`run_eval.py` now also prints each item's `reason` field (and each dropped capture's
reason) to the console per-case, so failures are diagnosable from the normal run output
without a bespoke debug script — per owner request, nothing is persisted to disk and
thinking-summary display was not requested (keeps cost/latency down).

One reproducible gap survived every model/effort combination tried: `fanout-oxide-hardware`
intermittently drops the SpaceX item from that newsletter's fan-out (passed in 2 of 4
runs). Worth a prompt-level look later — likely the SpaceX spectrum story loses out to
Oxide's funding story for attention in that batch — but not blocking, since it isn't tied
to the backend/model decision.

**First real Triage run — done (2026-10-27).** `tools/triage.py` ran against the live
35-capture inbox backlog (`claude-opus-5`, default effort): **88 classified items, 3
dropped**, written to `inbox/_triage/2026-10-27.json`; all 35 raw captures consumed and
removed, the permanent record intact in `sources/` untouched. Hand-reviewed and it holds
up well — in some ways better than the eval subset suggested:
- All 88 items cite real `sources/...` notes — zero hallucinated citations.
- Both TLDR signup-confirmation captures and the Zuckerberg rant correctly dropped as
  noise (this was the eval's most persistently flaky case — clean here).
- Cross-modality near-duplicates correctly merged: Oxide (2 sources), Nvidia/Reflection
  (2 sources), and a SpaceX item that merged **3 sources spanning two different
  newsletter issues** — a stronger dedup result than anything seen in the smaller eval
  subset, and specifically the case (`fanout-oxide-hardware`'s SpaceX miss) that was
  flaky across every eval run.
- All 17 `opinion` items carry a specific, falsifiable claim (named mechanism, number, or
  contrarian prediction) per the keep bar in `meta/taxonomy.md` — none read as mere
  restatement. One borderline case (a conference field report) still has a defensible
  reason attached, not a clear miss.
- `development_type` spread across 12 of 13 taxonomy values (only `shutdown` unused, as
  expected — no shutdown events in this batch); `ai` dominates domains as expected for
  this source mix.

Committed as one atomic commit (`triage: first real run...`) — the 35 deletions +
`inbox/_triage/2026-10-27.json` addition, nothing else mixed in, per rule 8.

Known, non-blocking items carried forward from Triage (unrelated to the Enrich work below):
- The `fanout-oxide-hardware` SpaceX eval gap **did not reproduce** in the real run — the
  SpaceX item merged correctly across 3 sources. Likely an artifact of the smaller eval
  subset; not worth chasing unless it recurs.
- `collect_readwise.py`'s `EXCERPT_WORD_LIMIT` (500 words) truncates 31 of 35 real
  captures before Triage ever sees them — a plausible source of future fan-out/dedup
  misses on long newsletters. Flagged, not acted on (owner chose current excerpts,
  revisit only if it causes real misses).

## Enrich (Stage 3) — built and committed this session (2026-10-28), eval NOT yet run

**Everything below is free/committed work. The eval costs real money and is the next
concrete action — see "Resume here" at the end of this section.**

Built, in 4 commits (`git log` has the full reasoning per commit):

1. **Split `meta/agent-instructions.md`** into per-stage files (see durable decisions
   above) — a prerequisite so `enrich.py` could load its own rules cleanly, the same way
   `triage.py` now does (`load_triage_rules()` rewritten to a plain file read + frontmatter
   strip, no more heading-slicing).
2. **`tools/enrich_resolve.py`** — pure entity-resolution logic, no API calls. For every
   entity string in a Triage item, decides: `matched` (exact name/alias match against a
   vault-wide index built by reusing `tools/lint.py`'s `load_note`/`iter_markdown`/
   `wikilink_targets`/`resolve_key`), `pending_second_mention` (clears the ≥2-mentions bar
   via an existing unresolved `[[link]]` **or** a prior fact already stored in
   `meta/pending-entities.md`), or `pending_first_mention` (stores the fact, creates
   nothing). Verified fact-fidelity round-trip exactly (a stored fact's text survives
   save/load unchanged) and real resolution against the live vault (`Figure AI`/`Brett
   Adcock` → matched, `Apptronik` → pending-second via an existing unresolved competitor
   link, `XPeng` → pending-first) — all free, no API calls.
3. **`tools/prompts/enrich.md` + `tools/enrich.py`** — the prompt interpolates
   `meta/agent-instructions/enrich.md`, `hard-rules.md`, and relevant `meta/schema.md`
   excerpts at runtime (same discipline as Triage: never restate rules in the prompt).
   Output is a **flat** Pydantic schema (`EnrichAction`, not a discriminated union) covering
   6 action types — `timeline_entry`, `frontmatter_patch`, `new_note`, `concept_link`,
   `key_link`, `skip` — with action-type-specific required fields enforced in Python
   (`validate_actions()`), not the JSON schema, because a discriminated union's `oneOf`
   shape is untested against this session's gateway and `extra="forbid"` was already a
   gateway-compatibility lesson learned the hard way during Triage. A Python hard-guard
   layer rejects anything violating a rule that must never break regardless of model
   output: no uncited timeline entry, **no opinion item ever gets a `timeline_entry`**
   (checked for both standalone and inside a `new_note`), no new-note name/alias collision,
   nothing in `meta/rejected-links.md`. Applying an action is a targeted text edit
   (timeline bullets inserted newest-first under the right `### YYYY` heading, frontmatter
   patched via a YAML round-trip) — **the model never writes a full file verbatim.**
   Defaults to preview-only; `--apply` is required for real writes and runs `tools/lint.py`
   on touched files before declaring success.
4. **`tools/evals/run_enrich_eval.py` + 5 golden cases** in `tools/evals/cases/enrich/`,
   built from real items in `inbox/_triage/2026-10-27.json` (selected by `item_ids`, not
   hand-written captures): `figure-series-c-existing-note` (routes to existing
   company+person, frontmatter rollup backed by the ledger entry), `apptronik-second-
   mention-new-note` (creates a note once the ≥2-mentions bar clears), `xpeng-first-
   mention-pending` (nothing created yet for a genuine first mention),
   `opinion-never-gets-timeline` (hard rule only — revised from an earlier draft that
   assumed the sole existing robotics thread, `Humanoid manipulation`, was a topical fit
   for a business-consolidation thesis; on inspection its curated scope is dexterous
   manipulation technique, not M&A — so the case only asserts what's guaranteed, not a
   debatable routing call), `incidental-mention-skipped` (no spurious Figure AI entry for
   an item about a different company's round). The eval scores the model's output *after*
   the same `validate_actions()` pass `--apply` runs — a rejected action never counts
   toward a case's score.

**A real scoring bug was caught and fixed before any live run**, same discipline as the
Triage build: an early version of the eval's `target_note_stem` check only read
`a.target_note`, but a `new_note` action has no `target_note` (it uses `new_note_path`) —
so "must not create a new note for X" checks would have silently never fired. Fixed, then
re-verified both the catch and the correct-behavior path against hand-built `EnrichAction`
fixtures, at zero cost.

**Verified this session, all free:** `--dry-run` against the real vault + real
`inbox/_triage/2026-10-27.json` (88 items) correctly resolved `Figure AI`/`Brett Adcock` as
matched and `Apptronik` as pending-second-mention; 19 new mocked tests for `enrich.py` +
12 for `enrich_resolve.py` (91/91 total with Triage's suite); lint holds at 0 errors
throughout; every eval check type verified against hand-built fixtures offline.

### Resume here — next concrete action

1. **Run `tools/evals/run_enrich_eval.py` for the first time.** Costs real money (expect a
   similar order of magnitude to Triage's ~$0.35–0.40/run, scaled to the eval's 5 cases
   covering ~4 items — likely cheaper than that). `source tools/.env && set -a` first.
   Default model is `claude-opus-5` (same as Triage settled on) — no model sweep has been
   done for Enrich yet; consider one if the Opus baseline isn't clean, following the same
   method as Triage's (`DESIGN.md` §2): compare scores, not just cost, before switching.
2. Iterate the prompt/cases against whatever the first run shows — per the Triage
   experience, a failing case is often a hand-label that's too strict, not a model error;
   check the actual proposed action before rewriting the prompt.
3. Once the eval score is solid, run `tools/enrich.py --input inbox/_triage/2026-10-27.json`
   (preview mode, the default) against the real 88-item backlog and **hand-review the
   printed diff** before ever passing `--apply` — this writes to permanent vault content,
   a materially higher-risk operation than Triage's disposable JSON output.
4. Only after a real `--apply` run has been reviewed: build the daily digest (Stage 4),
   which consumes Enrich's output and didn't exist to depend on before now.

Other options, lower priority:

- **(a) Bulk-seed (finish step 2)** — ~10–15 more evergreen concepts, ~20–40 companies,
  ~6–10 threads. Large review load; draft in batches into a scratch file for review before
  writing to the vault. Note: `technologies/` is currently **empty** (zero notes), which
  will make Enrich's "≥2 mentions" new-note rule fire constantly once it's built.
- **(c) Build `collect-tavily`** — needs a query list decided first (see
  `meta/ongoing-discussions.md`), then follow `collect_readwise.py`'s pattern (same
  `meta/collector-state.json`, same `type: capture` inbox output).
- **(d) Add `collect-youtube`** — needs a starter channel/video list first.

**Correction to a stale fact in this file:** the "3 Readwise onboarding articles" noted
below under `collect_readwise.py`'s first run were already removed in commit `6abfc3a`
(before this session) — the live inbox corpus is 35 captures, not 38.

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
