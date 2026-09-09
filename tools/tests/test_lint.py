"""Fixture-driven tests for tools/lint.py.

Each test builds a minimal in-memory vault under tmp_path, runs lint_vault(), and asserts
which rules fire. Invalid fixtures trigger exactly one rule where practical.
"""
import datetime as dt

import lint

TODAY = dt.date(2026, 9, 5)

LONG = ("This sentence exists only so the note clears the 120-character stub threshold "
        "comfortably and does not trip the stub warning during tests.")

VALID_CONCEPT = f"""---
type: concept
name: "Widget"
category: technique
maturity: established
created: 2026-01-01
updated: 2026-01-01
---
# Widget
## Definition
{LONG}
## How it works
How.
## Why it matters
Why.
"""

VALID_COMPANY = f"""---
type: company
name: "Acme"
status: active
sectors: [ai-tooling]
watchlist: false
created: 2026-01-01
updated: 2026-09-01
---
# Acme
## Summary
{LONG}
## What they do
Things.
## Timeline
### 2026
-
"""

VALID_SOURCE = """---
type: source
title: "A report"
publication: "Somewhere"
published: 2026-01-02
accessed: 2026-01-03
url: "https://example.com"
archive_url: "https://web.archive.org/x"
tier: secondary
---
# A report
## Extract
> quote
"""


def build(tmp_path, notes):
    for rel, content in notes.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


def run(tmp_path):
    return lint.lint_vault(tmp_path, today=TODAY)


def rules(findings, severity=None):
    return {f.rule for f in findings if severity is None or f.severity == severity}


# --------------------------------------------------------------------- clean baseline

def test_clean_vault_has_no_errors(tmp_path):
    build(tmp_path, {
        "concepts/Widget.md": VALID_CONCEPT,
        "companies/Acme.md": VALID_COMPANY,
        "sources/A report.md": VALID_SOURCE,
    })
    assert rules(run(tmp_path), lint.ERROR) == set()


# --------------------------------------------------------------------- frontmatter

def test_missing_type(tmp_path):
    build(tmp_path, {"companies/X.md": "---\nname: X\n---\n# X\n"})
    assert "missing-type" in rules(run(tmp_path), lint.ERROR)


def test_unknown_type(tmp_path):
    build(tmp_path, {"companies/X.md": "---\ntype: widgetco\nname: X\n---\n# X\n"})
    assert "unknown-type" in rules(run(tmp_path), lint.ERROR)


def test_no_frontmatter(tmp_path):
    build(tmp_path, {"companies/X.md": "# X\n\nno frontmatter here\n"})
    assert "frontmatter-invalid" in rules(run(tmp_path), lint.ERROR)


def test_frontmatter_bad_yaml(tmp_path):
    build(tmp_path, {"companies/X.md": "---\ntype: company\n  name: [oops\n---\n# X\n"})
    assert "frontmatter-invalid" in rules(run(tmp_path), lint.ERROR)


def test_duplicate_stem_across_types_is_error(tmp_path):
    person = """---
type: person
name: "Acme"
created: 2026-01-01
updated: 2026-01-01
---
# Acme
## Summary
Someone.
## Timeline
### 2026
-
"""
    build(tmp_path, {"companies/Acme.md": VALID_COMPANY, "people/Acme.md": person})
    found = run(tmp_path)
    dupes = {f.path for f in found if f.rule == "duplicate-name"}
    assert dupes == {"companies/Acme.md", "people/Acme.md"}
    assert all(f.severity == lint.ERROR for f in found if f.rule == "duplicate-name")


def test_meta_notes_sharing_a_filename_are_not_flagged(tmp_path):
    meta_note = "---\ntype: meta\nname: Section\nupdated: 2026-01-01\n---\n# Section\n"
    build(tmp_path, {"inbox/README.md": meta_note, "digests/README.md": meta_note})
    assert "duplicate-name" not in rules(run(tmp_path))


def test_duplicate_alias_is_error(tmp_path):
    concept_a = VALID_CONCEPT.replace('name: "Widget"', 'name: "Widget"\naliases: [Gizmo]')
    concept_b = VALID_CONCEPT.replace('name: "Widget"', 'name: "Sprocket"\naliases: [Gizmo]')
    build(tmp_path, {"concepts/Widget.md": concept_a, "concepts/Sprocket.md": concept_b})
    dupes = {f.path for f in run(tmp_path) if f.rule == "duplicate-name"}
    assert dupes == {"concepts/Widget.md", "concepts/Sprocket.md"}


# --------------------------------------------------------------------- schema

def test_missing_required_field(tmp_path):
    note = "---\ntype: company\nname: X\nstatus: active\nwatchlist: false\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n# X\n"
    build(tmp_path, {"companies/X.md": note})  # no `sectors`
    assert "missing-required-field" in rules(run(tmp_path), lint.ERROR)


def test_empty_required_field_counts_as_missing(tmp_path):
    note = VALID_COMPANY.replace("status: active", "status:")
    build(tmp_path, {"companies/Acme.md": note})
    assert "missing-required-field" in rules(run(tmp_path), lint.ERROR)


def test_bad_enum_value(tmp_path):
    note = VALID_COMPANY.replace("status: active", "status: zombie")
    build(tmp_path, {"companies/Acme.md": note})
    assert "bad-enum-value" in rules(run(tmp_path), lint.ERROR)


def test_bad_list_enum_value(tmp_path):
    note = """---
type: moc
name: "T"
kind: thread
domains: [ai, telepathy]
created: 2026-01-01
updated: 2026-01-01
---
# T
## Current state
s
## Timeline
### 2026
-
"""
    build(tmp_path, {"topics/T.md": note})
    assert "bad-enum-value" in rules(run(tmp_path), lint.ERROR)


def test_bad_field_type_sectors_not_list(tmp_path):
    note = VALID_COMPANY.replace("sectors: [ai-tooling]", "sectors: ai-tooling")
    build(tmp_path, {"companies/Acme.md": note})
    assert "bad-field-type" in rules(run(tmp_path), lint.ERROR)


def test_bad_field_type_domains_not_list(tmp_path):
    note = """---
type: moc
name: "T"
kind: thread
domains: ai
created: 2026-01-01
updated: 2026-01-01
---
# T
## Current state
s
## Timeline
### 2026
-
"""
    build(tmp_path, {"topics/T.md": note})
    assert "bad-field-type" in rules(run(tmp_path), lint.ERROR)


def test_bad_full_date_format(tmp_path):
    note = VALID_COMPANY.replace("updated: 2026-09-01", "updated: 2026/09/01")
    build(tmp_path, {"companies/Acme.md": note})
    assert "bad-date-format" in rules(run(tmp_path), lint.ERROR)


def test_year_date_accepts_bare_year(tmp_path):
    note = VALID_COMPANY.replace("created: 2026-01-01", "created: 2026-01-01\nfounded: 2021")
    build(tmp_path, {"companies/Acme.md": note})
    assert "bad-date-format" not in rules(run(tmp_path), lint.ERROR)


def test_year_date_rejects_junk(tmp_path):
    note = VALID_COMPANY.replace("created: 2026-01-01", "created: 2026-01-01\nfounded: last tuesday")
    build(tmp_path, {"companies/Acme.md": note})
    assert "bad-date-format" in rules(run(tmp_path), lint.ERROR)


# --------------------------------------------------------------------- links

def test_broken_source_link_is_error(tmp_path):
    note = VALID_COMPANY.replace(
        "### 2026\n-",
        "### 2026\n- 2026-02-01 — Did a thing. ([[sources/does-not-exist]]) #milestone",
    )
    build(tmp_path, {"companies/Acme.md": note})
    assert "broken-source-link" in rules(run(tmp_path), lint.ERROR)


def test_valid_source_link_ok(tmp_path):
    note = VALID_COMPANY.replace(
        "### 2026\n-",
        "### 2026\n- 2026-02-01 — Did a thing. ([[sources/A report]]) #milestone",
    )
    build(tmp_path, {"companies/Acme.md": note, "sources/A report.md": VALID_SOURCE})
    got = rules(run(tmp_path), lint.ERROR)
    assert "broken-source-link" not in got
    assert "uncited-timeline-bullet" not in got


def test_unresolved_nonsource_link_is_warning_not_error(tmp_path):
    note = VALID_COMPANY.replace("## Timeline", "## Competitors\n- [[Globex]]\n\n## Timeline")
    build(tmp_path, {"companies/Acme.md": note})
    found = run(tmp_path)
    assert "unresolved-link" in rules(found, lint.WARNING)
    assert "unresolved-link" not in rules(found, lint.ERROR)


def test_wikilinks_in_code_blocks_are_ignored(tmp_path):
    note = VALID_COMPANY.replace(
        "## What they do\nThings.",
        "## What they do\nThings. Example: `[[sources/xyz]]` and\n```\n[[sources/abc]]\n```",
    )
    build(tmp_path, {"companies/Acme.md": note})
    assert "broken-source-link" not in rules(run(tmp_path), lint.ERROR)


def test_alias_resolves_link(tmp_path):
    concept = VALID_CONCEPT.replace('name: "Widget"', 'name: "Widget"\naliases: [Gizmo]')
    company = VALID_COMPANY.replace("## What they do\nThings.",
                                    "## What they do\nBuilt on [[Gizmo]].")
    build(tmp_path, {"concepts/Widget.md": concept, "companies/Acme.md": company})
    assert "unresolved-link" not in rules(run(tmp_path), lint.WARNING)


# --------------------------------------------------------------------- timeline citations

def test_uncited_timeline_bullet_is_error(tmp_path):
    note = VALID_COMPANY.replace(
        "### 2026\n-",
        "### 2026\n- 2026-02-01 — Raised money. #milestone",
    )
    build(tmp_path, {"companies/Acme.md": note})
    assert "uncited-timeline-bullet" in rules(run(tmp_path), lint.ERROR)


def test_seed_note_allows_uncited_timeline(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false", "watchlist: false\nseed: true").replace(
        "### 2026\n-",
        "### 2026\n- 2026-02-01 — Raised money. #milestone",
    )
    build(tmp_path, {"companies/Acme.md": note})
    assert "uncited-timeline-bullet" not in rules(run(tmp_path), lint.ERROR)


# --------------------------------------------------------------------- warnings

def test_missing_section_warning(tmp_path):
    note = VALID_COMPANY.replace("## What they do\nThings.\n", "")
    build(tmp_path, {"companies/Acme.md": note})
    assert "missing-section" in rules(run(tmp_path), lint.WARNING)


def test_unknown_sector_warning(tmp_path):
    note = VALID_COMPANY.replace("sectors: [ai-tooling]", "sectors: [ai-tooling, teleportation]")
    build(tmp_path, {"companies/Acme.md": note})
    assert "unknown-sector" in rules(run(tmp_path), lint.WARNING)


def test_orphan_company_warned(tmp_path):
    build(tmp_path, {"companies/Acme.md": VALID_COMPANY})
    assert "orphan" in rules(run(tmp_path), lint.WARNING)


def test_concept_not_flagged_as_orphan(tmp_path):
    build(tmp_path, {"concepts/Widget.md": VALID_CONCEPT})
    assert "orphan" not in rules(run(tmp_path), lint.WARNING)


def test_seed_note_not_flagged_as_orphan(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false", "watchlist: false\nseed: true")
    build(tmp_path, {"companies/Acme.md": note})
    assert "orphan" not in rules(run(tmp_path), lint.WARNING)


def test_linked_note_not_orphan(tmp_path):
    company = VALID_COMPANY.replace("## What they do\nThings.",
                                    "## What they do\nUses [[Widget]].")
    build(tmp_path, {"concepts/Widget.md": VALID_CONCEPT, "companies/Acme.md": company})
    orphans = [f.path for f in run(tmp_path) if f.rule == "orphan"]
    assert "companies/Acme.md" in orphans  # Acme still orphan; Widget is a concept anyway


def test_stale_watchlist_warning(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false", "watchlist: true").replace(
        "updated: 2026-09-01", "updated: 2026-01-01")
    build(tmp_path, {"companies/Acme.md": note})
    assert "stale-watchlist" in rules(run(tmp_path), lint.WARNING)


def test_fresh_watchlist_not_stale(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false", "watchlist: true")
    build(tmp_path, {"companies/Acme.md": note})
    assert "stale-watchlist" not in rules(run(tmp_path), lint.WARNING)


def test_missing_archive_warning(tmp_path):
    note = VALID_SOURCE.replace('archive_url: "https://web.archive.org/x"', 'archive_url: ""')
    build(tmp_path, {"sources/A report.md": note})
    assert "missing-archive" in rules(run(tmp_path), lint.WARNING)


def test_unsupported_volatile_field_warning(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false", "watchlist: false\nstage: series-a")
    build(tmp_path, {"companies/Acme.md": note})
    assert "unsupported-volatile-field" in rules(run(tmp_path), lint.WARNING)


def test_volatile_field_ok_when_seed(tmp_path):
    note = VALID_COMPANY.replace("watchlist: false",
                                 "watchlist: false\nseed: true\nstage: series-a")
    build(tmp_path, {"companies/Acme.md": note})
    assert "unsupported-volatile-field" not in rules(run(tmp_path), lint.WARNING)


def test_stub_warning(tmp_path):
    note = """---
type: concept
name: "Thin"
category: technique
maturity: emerging
created: 2026-01-01
updated: 2026-01-01
---
# Thin
## Definition
## How it works
## Why it matters
"""
    build(tmp_path, {"concepts/Thin.md": note})
    assert "stub" in rules(run(tmp_path), lint.WARNING)


# --------------------------------------------------------------------- driver behaviour

def test_only_filter_scopes_findings(tmp_path):
    build(tmp_path, {
        "companies/Acme.md": VALID_COMPANY.replace("status: active", "status: zombie"),
        "concepts/Widget.md": VALID_CONCEPT.replace("category: technique", "category: bogus"),
    })
    only = [tmp_path / "companies/Acme.md"]
    found = lint.lint_vault(tmp_path, only=only, today=TODAY)
    assert {f.path for f in found} == {"companies/Acme.md"}


def test_report_render_has_frontmatter_and_counts(tmp_path):
    build(tmp_path, {"companies/Acme.md": VALID_COMPANY.replace("status: active", "status: zombie")})
    found = run(tmp_path)
    report = lint.render_report(found, TODAY)
    assert report.startswith("---\ntype: meta")
    assert "**Errors:**" in report
    assert "bad-enum-value" in report
