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

### What it checks

**Errors (fail the run):** invalid/missing frontmatter, unknown `type`, missing required
fields, bad enum values, bad date formats, broken `[[sources/...]]` citations, uncited
dated `## Timeline` entries (non-`seed` notes).

**Warnings:** unresolved non-source `[[links]]` (markers or typos — reviewed, not fixed
blindly), missing `## sections`, unknown company sectors, orphans (excluding concepts and
`seed:` notes), stubs, stale watchlist entries, `unsupported-volatile-field`, missing
`archive_url` on sources.

Not yet implemented (needs git diff / network — see `meta/agent-instructions.md`):
curated-block tamper detection, dead external link checking.
