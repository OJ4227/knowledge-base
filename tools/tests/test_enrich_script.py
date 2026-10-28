"""Tests for tools/enrich.py against a mocked Anthropic client — no real API calls."""
import json

import pytest

import enrich as en
import enrich_resolve as er


COMPANY_TEMPLATE = """---
type: company
name: "<note name>"
aliases: []
status:
founded:
hq: ""
sectors: []
stage:
total_funding_usd:
last_round:
people: []
watchlist: false
priority:
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <note name>

## Summary

<!-- curated -->

## What they do

<!-- curated -->

## Key milestones

## Timeline

### YYYY

-

## Funding history

## People

## Competitors

## Open questions
"""

TOPIC_TEMPLATE = """---
type: moc
name: "<note name>"
aliases: []
kind: thread
domains: []
concepts: []
related: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <note name>

<!-- curated intro -->

## Current state

## Timeline

### YYYY

-

## Key entities

## Key links
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(en, "ROOT", tmp_path)
    monkeypatch.setattr(en, "PROMPT_PATH", tmp_path / "tools" / "prompts" / "enrich.md")
    monkeypatch.setattr(en, "ENRICH_RULES_PATH",
                        tmp_path / "meta" / "agent-instructions" / "enrich.md")
    monkeypatch.setattr(en, "HARD_RULES_PATH",
                        tmp_path / "meta" / "agent-instructions" / "hard-rules.md")
    monkeypatch.setattr(en, "SCHEMA_PATH", tmp_path / "meta" / "schema.md")
    monkeypatch.setattr(en, "REJECTED_LINKS_PATH", tmp_path / "meta" / "rejected-links.md")
    monkeypatch.setattr(en, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(er, "PENDING_ENTITIES_PATH", tmp_path / "meta" / "pending-entities.md")

    write(tmp_path / "tools" / "prompts" / "enrich.md",
          "RULES:\n{enrich_rules}\nHARD:\n{hard_rules}\nSCHEMA:\n{schema_excerpts}\n"
          "ITEMS:\n{items}\n")
    write(tmp_path / "meta" / "agent-instructions" / "enrich.md",
          "---\ntype: meta\n---\n\n# Enrich\n\nEnrich rules here.\n")
    write(tmp_path / "meta" / "agent-instructions" / "hard-rules.md",
          "---\ntype: meta\n---\n\n# Hard rules\n\nHard rules here.\n")
    write(tmp_path / "meta" / "schema.md",
          "# Schema\n\n## `company`\n\ncompany schema here\n\n## `source`\n\nirrelevant\n\n"
          "## Timeline entry format\n\ntimeline format here\n")
    write(tmp_path / "templates" / "company.md", COMPANY_TEMPLATE)
    write(tmp_path / "templates" / "moc.md", TOPIC_TEMPLATE)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    return tmp_path


def make_input(tmp_path, items):
    path = tmp_path / "inbox" / "_triage" / "2026-10-27.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_date": "2026-10-27", "captures_consumed": [],
                                "dropped": [], "items": items}), encoding="utf-8")
    return path


def figure_ai_note(tmp_path, body_extra=""):
    text = COMPANY_TEMPLATE.replace('name: "<note name>"', 'name: "Figure AI"') \
        .replace("aliases: []", "aliases: [Figure]") \
        .replace("# <note name>", "# Figure AI")
    if body_extra:
        text = text.replace("## Competitors\n", f"## Competitors\n\n{body_extra}\n")
    return write(tmp_path / "companies" / "Figure AI.md", text)


def item(id="x", title="Title", summary="Summary", domains=None, development_type="funding",
         entities=None, concepts=None, sources=None, claim_status="confirmed", reason=None):
    return {
        "id": id, "title": title, "summary": summary,
        "domains": domains or ["business"], "development_type": development_type,
        "entities": entities or [], "concepts": concepts or [],
        "sources": sources or ["[[sources/a]]"], "claim_status": claim_status,
        "reason": reason,
    }


# --------------------------------------------------------------------------- prompt assembly

def test_build_prompt_interpolates_all_placeholders(tmp_path):
    figure_ai_note(tmp_path)
    items = [en.TriageItemView(**item(id="figure-c", entities=["Figure AI"]))]
    index = er.build_vault_index(tmp_path)
    pending = er.PendingStore()
    prompt = en.build_prompt(items, index, pending)
    assert "Enrich rules here." in prompt
    assert "Hard rules here." in prompt
    assert "company schema here" in prompt
    assert "timeline format here" in prompt
    assert "figure-c" in prompt
    assert "matched: companies/Figure AI.md" in prompt


def test_dry_run_makes_no_api_call(tmp_path, monkeypatch):
    input_path = make_input(tmp_path, [item()])

    def fail_if_called(*a, **k):
        raise AssertionError("API should not be called on --dry-run")
    monkeypatch.setattr(en.tg.anthropic, "Anthropic", fail_if_called)

    rc = en.main(["--input", str(input_path), "--dry-run"])
    assert rc == 0


# --------------------------------------------------------------------------- hard guards

def test_timeline_entry_rejected_without_sources(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    bad = en.EnrichAction(
        action_type="timeline_entry", item_id="x", target_note="companies/Figure AI.md",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            sources=[]),
    )
    accepted, rejected = en.validate_actions([bad], index, set(), set())
    assert accepted == []
    assert "zero sources" in rejected[0].reason


def test_timeline_entry_rejected_for_opinion_item(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="timeline_entry", item_id="opinion-item",
        target_note="companies/Figure AI.md",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), {"opinion-item"})
    assert accepted == []
    assert "opinion" in rejected[0].reason.lower()


def test_timeline_entry_rejected_for_unknown_target(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="timeline_entry", item_id="x", target_note="companies/Nonexistent.md",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "not found in vault index" in rejected[0].reason


def test_new_note_rejected_on_name_collision(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="new_note", item_id="x", new_note_type="company",
        new_note_path="companies/Figure.md",  # "Figure" is an existing alias
        new_note_frontmatter_yaml="name: Figure\n",
        new_note_timeline_entries=[en.TimelineEntrySpec(
            date="2026-01-01", text="Fact.", tag="routine", sources=["[[sources/a]]"])],
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "collision" in rejected[0].reason


def test_new_note_accepted_for_genuinely_new_name(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="new_note", item_id="x", new_note_type="company",
        new_note_path="companies/Apptronik.md",
        new_note_frontmatter_yaml="name: Apptronik\nsectors: [robotics]\nwatchlist: false\nstatus: active\n",
        new_note_timeline_entries=[en.TimelineEntrySpec(
            date="2026-01-01", text="Fact.", tag="routine", sources=["[[sources/a]]"])],
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert len(accepted) == 1
    assert rejected == []


def test_concept_link_rejected_when_concept_note_missing(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(action_type="concept_link", item_id="x",
                             target_note="companies/Figure AI.md", concept="nonexistent concept")
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "never auto-create" in rejected[0].reason


def test_concept_link_respects_rejected_links(tmp_path):
    figure_ai_note(tmp_path)
    write(tmp_path / "concepts" / "Embodied intelligence.md",
          '---\ntype: concept\nname: "Embodied intelligence"\ncategory: technique\n'
          'maturity: emerging\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\nBody.\n')
    index = er.build_vault_index(tmp_path)
    rejected_pairs = {(lint_key("Figure AI"), lint_key("Embodied intelligence"))}
    action = en.EnrichAction(action_type="concept_link", item_id="x",
                             target_note="companies/Figure AI.md",
                             concept="Embodied intelligence")
    accepted, rejected = en.validate_actions([action], index, rejected_pairs, set())
    assert accepted == []
    assert "rejected-links" in rejected[0].reason


def lint_key(name):
    import lint
    return lint.resolve_key(name)


def test_skip_action_always_accepted(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(action_type="skip", item_id="x", reason="incidental mention")
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert len(accepted) == 1
    assert rejected == []


# --------------------------------------------------------------------------- applying actions

def test_apply_timeline_entry_inserts_newest_first_under_year(tmp_path):
    path = figure_ai_note(tmp_path)
    entry_old = en.TimelineEntrySpec(date="2026-01-01", text="Older fact.", tag="routine",
                                     sources=["[[sources/a]]"])
    entry_new = en.TimelineEntrySpec(date="2026-06-01", text="Newer fact.", tag="milestone",
                                     sources=["[[sources/b]]"])
    en.apply_timeline_entry(path, entry_old)
    en.apply_timeline_entry(path, entry_new)

    body = path.read_text()
    newer_idx = body.index("Newer fact.")
    older_idx = body.index("Older fact.")
    assert newer_idx < older_idx  # newest first
    assert "### 2026" in body
    assert "#milestone" in body
    assert "[[sources/a]]" in body and "[[sources/b]]" in body


def test_apply_timeline_entry_with_claim_tag(tmp_path):
    path = figure_ai_note(tmp_path)
    entry = en.TimelineEntrySpec(date="2026-01-01", text="Rumored fact.", tag="routine",
                                 claim_tag="claim/rumored", sources=["[[sources/a]]"])
    en.apply_timeline_entry(path, entry)
    body = path.read_text()
    assert "#routine #claim/rumored" in body


def test_apply_timeline_entry_bumps_updated(tmp_path):
    path = figure_ai_note(tmp_path)
    entry = en.TimelineEntrySpec(date="2026-06-01", text="Fact.", tag="routine",
                                 sources=["[[sources/a]]"])
    en.apply_timeline_entry(path, entry)
    import yaml, lint
    fm, _ = lint.split_frontmatter(path.read_text())
    data = yaml.safe_load(fm)
    assert data["updated"] != "YYYY-MM-DD"


def test_apply_frontmatter_patch_sets_field_and_bumps_updated(tmp_path):
    path = figure_ai_note(tmp_path)
    en.apply_frontmatter_patch(path, "stage", "series-c")
    import yaml, lint
    fm, _ = lint.split_frontmatter(path.read_text())
    data = yaml.safe_load(fm)
    assert data["stage"] == "series-c"
    assert data["updated"] != "YYYY-MM-DD"


def test_apply_frontmatter_patch_does_not_disturb_body(tmp_path):
    path = figure_ai_note(tmp_path)
    before = path.read_text().split("---", 2)[2]
    en.apply_frontmatter_patch(path, "stage", "series-c")
    after = path.read_text().split("---", 2)[2]
    assert before == after


def test_create_new_note_writes_frontmatter_and_timeline(tmp_path):
    action = en.EnrichAction(
        action_type="new_note", item_id="x", new_note_type="company",
        new_note_path="companies/Apptronik.md",
        new_note_frontmatter_yaml="name: Apptronik\nsectors: [robotics]\nwatchlist: false\nstatus: active\n",
        new_note_timeline_entries=[
            en.TimelineEntrySpec(date="2025-01-01", text="First fact.", tag="routine",
                                 sources=["[[sources/a]]"]),
            en.TimelineEntrySpec(date="2026-01-01", text="Second fact.", tag="milestone",
                                 sources=["[[sources/b]]"]),
        ],
    )
    out_path = en.create_new_note(action)
    text = out_path.read_text()
    import yaml, lint
    fm, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm)
    assert data["name"] == "Apptronik"
    assert data["sectors"] == ["robotics"]
    assert "created" in data and "updated" in data
    assert "First fact." in body and "Second fact." in body
    # newest first
    assert body.index("Second fact.") < body.index("First fact.")


def test_create_new_note_preserves_both_pending_and_new_facts(tmp_path):
    """Fact fidelity: a prior stored fact promoted into a new note must survive verbatim."""
    stored_text = ("- 2025-03-12 — XPeng planned up to $13.8B humanoid robot investment. "
                   "([[sources/xpeng]]) #routine #claim/reported")
    action = en.EnrichAction(
        action_type="new_note", item_id="x", new_note_type="company",
        new_note_path="companies/XPeng.md",
        new_note_frontmatter_yaml="name: XPeng\nsectors: [robotics]\nwatchlist: false\nstatus: active\n",
        new_note_timeline_entries=[
            en.TimelineEntrySpec(date="2025-03-12", text="XPeng planned up to $13.8B humanoid "
                                 "robot investment.", tag="routine", claim_tag="claim/reported",
                                 sources=["[[sources/xpeng]]"]),
        ],
    )
    out_path = en.create_new_note(action)
    body = out_path.read_text()
    assert stored_text in body


# --------------------------------------------------------------------------- rejected-links parsing

def test_load_rejected_pairs(tmp_path):
    write(tmp_path / "meta" / "rejected-links.md",
          "---\ntype: meta\n---\n\n# Rejected\n\n"
          "- 2026-01-01 — [[Figure AI]] ↔ [[Embodied intelligence]] — link — not relevant\n")
    pairs = en.load_rejected_pairs(tmp_path / "meta" / "rejected-links.md")
    assert (lint_key("Figure AI"), lint_key("Embodied intelligence")) in pairs
    assert (lint_key("Embodied intelligence"), lint_key("Figure AI")) in pairs


def test_load_rejected_pairs_missing_file(tmp_path):
    pairs = en.load_rejected_pairs(tmp_path / "does-not-exist.md")
    assert pairs == set()
