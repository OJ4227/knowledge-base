# tools/

Vault tooling. Not part of the Obsidian vault (excluded in `.obsidian/app.json`).

## `lint.py`

Deterministic checks over the vault — the machine-checkable half of `meta/schema.md`.
Never edits notes.

```bash
# one-time
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-dev.txt

# run
.venv/bin/python tools/lint.py            # whole vault; writes meta/health/lint-report.md
.venv/bin/python tools/lint.py --strict   # warnings also fail
.venv/bin/python tools/lint.py companies/Anthropic.md   # report on one file

# tests
.venv/bin/pytest tools/
```

Exit code is 1 if there are errors (or, with `--strict`, any warnings), else 0 —
suitable for a pre-commit hook or CI.

### Pre-commit hook

A hook that blocks commits on lint errors lives at `tools/hooks/pre-commit`. It's not
active until each clone opts in (one-time, per machine):

```bash
git config core.hooksPath tools/hooks
```

The hook only fails on errors, not warnings, and requires `.venv` to already exist
(it prints setup instructions instead of guessing).

### What it checks

**Errors (fail the run):** invalid/missing frontmatter, unknown `type`, missing required
fields, bad enum values, bad field types (e.g. `sectors:` not a YAML list), bad date
formats, broken `[[sources/...]]` citations, uncited dated `## Timeline` entries
(non-`seed` notes), duplicate names/aliases across content notes (ambiguous `[[link]]`
resolution).

**Warnings:** unresolved non-source `[[links]]` (markers or typos — reviewed, not fixed
blindly), missing `## sections`, unknown company sectors, orphans (excluding concepts and
`seed:` notes), stubs, stale watchlist entries, `unsupported-volatile-field`, missing
`archive_url` on sources.

Not yet implemented (needs git diff / network — see `meta/agent-instructions.md`):
curated-block tamper detection, dead external link checking.

## `collect_readwise.py`

Stage 1 collector for the Readwise Reader API (RSS feeds + email newsletters, including any
Twitter/X List subscriptions set up in Reader — see `DESIGN.md` §7). Fetches documents
updated since the last run, writes a `sources/` note + local HTML snapshot per item, and a
raw `inbox/` capture for Triage.

```bash
# one-time: copy tools/.env.example to tools/.env and fill in READWISE_TOKEN
# (get it from https://readwise.io/access_token)

.venv/bin/pip install -r tools/requirements-dev.txt  # installs requests too

source tools/.env && set -a  # or: export $(cat tools/.env | xargs), any way to load it
.venv/bin/python tools/collect_readwise.py              # real run
.venv/bin/python tools/collect_readwise.py --dry-run    # report only, writes nothing
```

State (`meta/collector-state.json`) is **committed to the repo**, not git-ignored — so
whichever machine or CI runner executes this next picks up exactly where the last run left
off (see `meta/ongoing-discussions.md` → "Production scheduling / collector hosting").

No web.archive.org submission yet (needs separate archive.org credentials) — `archive_url`
is left blank, which lint reports as a non-blocking `missing-archive` warning.
