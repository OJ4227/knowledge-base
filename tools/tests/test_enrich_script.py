"""Tests for tools/enrich.py against a mocked Anthropic client — no real API calls."""
import json

import pytest
from pydantic import ValidationError

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
    monkeypatch.setattr(en, "TAXONOMY_PATH", tmp_path / "meta" / "taxonomy.md")
    monkeypatch.setattr(en, "REJECTED_LINKS_PATH", tmp_path / "meta" / "rejected-links.md")
    monkeypatch.setattr(en, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(en, "PLAN_DIR", tmp_path / "meta" / "review" / "enrich-plans")
    monkeypatch.setattr(er, "PENDING_ENTITIES_PATH", tmp_path / "meta" / "pending-entities.md")

    write(tmp_path / "tools" / "prompts" / "enrich.md",
          "RULES:\n{enrich_rules}\nHARD:\n{hard_rules}\nSCHEMA:\n{schema_excerpts}\n"
          "SECTORS:\n{sector_vocabulary}\nITEMS:\n{items}\n")
    write(tmp_path / "meta" / "agent-instructions" / "enrich.md",
          "---\ntype: meta\n---\n\n# Enrich\n\nEnrich rules here.\n")
    write(tmp_path / "meta" / "agent-instructions" / "hard-rules.md",
          "---\ntype: meta\n---\n\n# Hard rules\n\nHard rules here.\n")
    write(tmp_path / "meta" / "schema.md",
          "# Schema\n\n## `company`\n\ncompany schema here\n\n## `source`\n\nirrelevant\n\n"
          "## Timeline entry format\n\ntimeline format here\n")
    write(tmp_path / "meta" / "taxonomy.md",
          "# Taxonomy\n\n## Company sectors (`sectors:` field)\n\n"
          "`foundation-models` · `ai-agents`\n\n## Starter threads\n")
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
    assert "foundation-models" in prompt
    assert "figure-c" in prompt
    assert "matched: companies/Figure AI.md" in prompt


def test_build_prompt_parts_keep_items_out_of_cacheable_prefix(tmp_path):
    items = [en.TriageItemView(**item(id="changing-item", entities=["XPeng"]))]
    static_prompt, items_prompt = en.build_prompt_parts(
        items, er.build_vault_index(tmp_path), er.PendingStore()
    )
    assert "Enrich rules here." in static_prompt
    assert "changing-item" not in static_prompt
    assert "changing-item" in items_prompt


def test_dry_run_makes_no_api_call(tmp_path, monkeypatch):
    input_path = make_input(tmp_path, [item()])

    def fail_if_called(*a, **k):
        raise AssertionError("API should not be called on --dry-run")
    monkeypatch.setattr(en.tg.anthropic, "Anthropic", fail_if_called)

    rc = en.main(["--input", str(input_path), "--dry-run"])
    assert rc == 0


# --------------------------------------------------------------------------- plan artifacts

def test_preview_writes_validated_plan_without_vault_content(tmp_path, monkeypatch):
    input_path = make_input(tmp_path, [item(id="x")])
    plan_path = tmp_path / "review" / "plan.json"
    monkeypatch.setattr(en.tg, "build_client", lambda: object())
    monkeypatch.setattr(
        en, "request_actions",
        lambda *args, **kwargs: [
            en.EnrichAction(action_type="skip", item_id="x", reason="No relevant route.")
        ],
    )

    rc = en.main(["--input", str(input_path), "--plan-out", str(plan_path)])

    assert rc == 0
    plan = en.load_plan(plan_path)
    assert plan.input.path == "inbox/_triage/2026-10-27.json"
    assert plan.actions[0].reason == "No relevant route."
    assert plan.output_schema_sha256 == en.output_schema_sha256()
    assert not er.PENDING_ENTITIES_PATH.exists()


def test_preview_records_rejections_but_excludes_them_from_actions(tmp_path, monkeypatch):
    input_path = make_input(tmp_path, [item(id="x")])
    plan_path = tmp_path / "review" / "plan.json"
    monkeypatch.setattr(en.tg, "build_client", lambda: object())
    monkeypatch.setattr(en, "request_actions", lambda *args, **kwargs: [])

    rc = en.main(["--input", str(input_path), "--plan-out", str(plan_path)])

    assert rc == 0
    plan = en.load_plan(plan_path)
    assert plan.actions == []
    assert len(plan.rejections) == 1
    assert plan.rejections[0].reason == "item has no action in any output bucket"


def test_plan_fingerprint_detects_changed_and_added_vault_files(tmp_path):
    input_path = make_input(tmp_path, [item(id="x")])
    plan = en.build_plan(input_path, "model", "high", [])
    figure_path = figure_ai_note(tmp_path)

    problems = en.verify_plan_is_current(plan)

    assert any("vault state changed" in problem for problem in problems)
    assert any("companies/Figure AI.md" in problem for problem in problems)
    figure_path.unlink()

    write(tmp_path / "meta" / "schema.md",
          (tmp_path / "meta" / "schema.md").read_text() + "\nchanged\n")
    problems = en.verify_plan_is_current(plan)
    assert any("meta/schema.md" in problem for problem in problems)


def test_plan_fingerprint_detects_changed_triage_input(tmp_path):
    input_path = make_input(tmp_path, [item(id="x")])
    plan = en.build_plan(input_path, "model", "high", [])
    input_path.write_text('{"items": []}', encoding="utf-8")

    problems = en.verify_plan_is_current(plan)

    assert "input file changed: inbox/_triage/2026-10-27.json" in problems


def test_plan_detects_actions_changed_after_preview(tmp_path):
    input_path = make_input(tmp_path, [item(id="x")])
    plan = en.build_plan(input_path, "model", "high", [])
    plan.actions.append(
        en.EnrichAction(action_type="skip", item_id="x", reason="Added later.")
    )

    problems = en.verify_plan_is_current(plan)

    assert "plan actions changed after preview" in problems


def test_apply_plan_uses_exact_actions_without_api_call(tmp_path, monkeypatch):
    write(tmp_path / "sources" / "a.md",
          "---\ntype: source\ntitle: A\npublication: Test\nauthors: []\n"
          "published: 2026-01-01\naccessed: 2026-01-01\nurl: https://example.com\n"
          "archive_url: ''\nlocal_copy: ''\ntier: primary\n---\n\n## Extract\n\nFact.\n")
    input_path = make_input(tmp_path, [item(id="x", entities=["XPeng"])])
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(
            date="2026-01-01", text="Exact reviewed fact.", tag="routine",
            claim_tag="", sources=["[[sources/a]]"],
        ),
    )
    plan_path = tmp_path / "review" / "plan.json"
    en.write_plan(en.build_plan(input_path, "model", "high", [action]), plan_path)

    def fail_if_called():
        raise AssertionError("apply must not construct an API client")
    monkeypatch.setattr(en.tg, "build_client", fail_if_called)

    rc = en.main(["--apply-plan", str(plan_path)])

    assert rc == 0
    assert "Exact reviewed fact." in er.PENDING_ENTITIES_PATH.read_text()


def test_apply_stale_plan_fails_before_writing(tmp_path):
    input_path = make_input(tmp_path, [item(id="x", entities=["XPeng"])])
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(
            date="2026-01-01", text="Must not be written.", tag="routine",
            claim_tag="", sources=["[[sources/a]]"],
        ),
    )
    plan_path = tmp_path / "review" / "plan.json"
    en.write_plan(en.build_plan(input_path, "model", "high", [action]), plan_path)
    figure_ai_note(tmp_path)

    rc = en.main(["--apply-plan", str(plan_path)])

    assert rc == 1
    assert not er.PENDING_ENTITIES_PATH.exists()


def test_write_plan_refuses_to_overwrite(tmp_path):
    input_path = make_input(tmp_path, [item(id="x")])
    plan = en.build_plan(input_path, "model", "high", [])
    plan_path = tmp_path / "review" / "plan.json"
    en.write_plan(plan, plan_path)

    with pytest.raises(FileExistsError):
        en.write_plan(plan, plan_path)


def test_amend_plan_reroutes_selected_new_note_facts_to_planned_owner(tmp_path):
    input_path = make_input(tmp_path, [item(id="x")])
    owner = en.EnrichAction(
        action_type="new_note", item_id="owner", entity="OpenAI",
        target_note="companies/OpenAI.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="type: company\nname: OpenAI\nstatus: active\n"
                             "sectors: [foundation-models]\nwatchlist: true\n"
                             "created: 2026-01-01\nupdated: 2026-01-01\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Owner fact.", tag="routine",
                claim_tag="", sources=["[[sources/a]]"])],
        ),
    )
    product = en.EnrichAction(
        action_type="new_note", item_id="product", entity="ChatGPT",
        target_note="technologies/ChatGPT.md",
        new_note=en.NewNoteSpec(
            type="technology",
            frontmatter_yaml="type: technology\nname: ChatGPT\ncategory: model\n"
                             "status: released\nfirst_seen: 2026-01-01\n"
                             "maturity: mainstream\ncreated: 2026-01-01\n"
                             "updated: 2026-01-01\n",
            timeline_entries=[
                en.TimelineEntrySpec(
                    date="2026-02-01", text="Product event.", tag="milestone",
                    claim_tag="", sources=["[[sources/b]]"]),
                en.TimelineEntrySpec(
                    date="2026-01-01", text="Duplicate owner event.", tag="routine",
                    claim_tag="", sources=["[[sources/a]]"]),
            ],
        ),
    )
    source_path = tmp_path / "review" / "source.json"
    output_path = tmp_path / "review" / "amended.json"
    en.write_plan(
        en.build_plan(input_path, "model", "high", [owner, product]),
        source_path,
    )
    en.PROMPT_PATH.write_text(en.PROMPT_PATH.read_text() + "\npolicy changed\n")

    amended = en.amend_saved_plan(
        source_path,
        output_path,
        [("ChatGPT", "companies/OpenAI.md", [0], "Products live on owner pages.")],
    )

    assert source_path.exists()
    assert [action.action_type for action in amended.actions] == [
        "new_note", "timeline_entry",
    ]
    assert amended.actions[1].target_note == "companies/OpenAI.md"
    assert amended.actions[1].timeline_entry.text == "Product event."
    assert amended.amendments[0].entity == "ChatGPT"
    assert en.verify_plan_is_current(amended) == []


def test_reroute_can_drop_new_note_when_owner_action_already_covers_fact(tmp_path):
    owner = en.EnrichAction(
        action_type="new_note", item_id="owner", entity="OpenAI",
        target_note="companies/OpenAI.md",
        new_note=en.NewNoteSpec(
            type="company", frontmatter_yaml="type: company\nname: OpenAI\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Owner fact.", tag="routine",
                claim_tag="", sources=["[[sources/a]]"])],
        ),
    )
    product = en.EnrichAction(
        action_type="new_note", item_id="product", entity="ChatGPT",
        target_note="technologies/ChatGPT.md",
        new_note=en.NewNoteSpec(
            type="technology", frontmatter_yaml="type: technology\nname: ChatGPT\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Duplicate fact.", tag="routine",
                claim_tag="", sources=["[[sources/a]]"])],
        ),
    )
    pending_product = en.EnrichAction(
        action_type="pending_fact", item_id="earlier", entity="ChatGPT",
        timeline_entry=en.TimelineEntrySpec(
            date="2025-12-01", text="Earlier product fact.", tag="routine",
            claim_tag="", sources=["[[sources/a]]"],
        ),
    )
    original_actions = [owner, pending_product, product]
    plan = en.EnrichPlan(
        format_version=1,
        created_at="2026-01-01T00:00:00+00:00",
        input=en.PlanInput(path="input.json", sha256="x"),
        model="model",
        effort="high",
        output_schema_sha256="x",
        actions_sha256=en.actions_sha256(original_actions),
        rejections_sha256=en.rejections_sha256([]),
        state=en.StateFingerprint(algorithm="sha256", digest="x", files={}),
        actions=original_actions,
        rejections=[],
    )

    en.reroute_new_note(
        plan, "ChatGPT", "companies/OpenAI.md", [],
        "Owner action already covers the fact.",
    )

    assert plan.actions == [owner]
    assert plan.amendments[0].kept_timeline_indexes == []
    assert plan.amendments[0].removed_pending_fact_count == 1


# --------------------------------------------------------------------------- typed output schema

def empty_result(**overrides):
    data = {
        "timeline_entries": [],
        "frontmatter_patches": [],
        "new_notes": [],
        "concept_links": [],
        "key_links": [],
        "pending_facts": [],
        "skips": [],
    }
    data.update(overrides)
    return data


def test_output_schema_requires_every_typed_bucket_and_has_no_anyof():
    schema = en.EnrichResult.model_json_schema()
    assert set(schema["required"]) == set(empty_result())
    assert "anyOf" not in json.dumps(schema)

    pending = schema["$defs"]["PendingFactAction"]
    assert set(pending["required"]) == {"item_id", "entity", "timeline_entry"}
    timeline = schema["$defs"]["TimelineEntrySpec"]
    assert set(timeline["required"]) == {"date", "text", "tag", "claim_tag", "sources"}
    assert timeline["properties"]["sources"]["minItems"] == 1


def test_pending_fact_cannot_omit_or_empty_its_timeline_entry():
    missing = empty_result(pending_facts=[{"item_id": "x", "entity": "XPeng"}])
    with pytest.raises(ValidationError):
        en.EnrichResult.model_validate(missing)

    empty_sources = empty_result(pending_facts=[{
        "item_id": "x",
        "entity": "XPeng",
        "timeline_entry": {
            "date": "2026-01-01", "text": "Fact.", "tag": "routine",
            "claim_tag": "", "sources": [],
        },
    }])
    with pytest.raises(ValidationError):
        en.EnrichResult.model_validate(empty_sources)


def test_typed_buckets_normalize_in_deterministic_order():
    result = en.EnrichResult.model_validate(empty_result(
        timeline_entries=[{
            "item_id": "x", "target_note": "companies/Figure AI.md",
            "timeline_entry": {
                "date": "2026-01-01", "text": "Fact.", "tag": "routine",
                "claim_tag": "", "sources": ["[[sources/a]]"],
            },
        }],
        pending_facts=[{
            "item_id": "y", "entity": "XPeng",
            "timeline_entry": {
                "date": "2026-01-01", "text": "Fact.", "tag": "routine",
                "claim_tag": "", "sources": ["[[sources/a]]"],
            },
        }],
        skips=[{"item_id": "z", "reason": "No action."}],
    ))
    actions = en.normalize_actions(result)
    assert [a.action_type for a in actions] == ["timeline_entry", "pending_fact", "skip"]


# --------------------------------------------------------------------------- batching and preview state

def test_make_batches_separates_repeated_unresolved_entity(tmp_path):
    index = er.build_vault_index(tmp_path)
    items = [
        en.TriageItemView(**item(id="first", entities=["XPeng"])),
        en.TriageItemView(**item(id="second", entities=["XPeng"])),
    ]
    batches = en.make_batches(items, batch_size=4, index=index)
    assert [[i.id for i in batch] for batch in batches] == [["first"], ["second"]]


def test_make_batches_respects_entity_budget(tmp_path):
    index = er.build_vault_index(tmp_path)
    items = [
        en.TriageItemView(**item(id="first", entities=["A", "B", "C"])),
        en.TriageItemView(**item(id="second", entities=["D", "E", "F"])),
    ]
    batches = en.make_batches(items, batch_size=12, index=index, max_entities=5)
    assert [[i.id for i in batch] for batch in batches] == [["first"], ["second"]]


def test_cross_batch_pending_fact_makes_next_mention_eligible(tmp_path):
    index = er.build_vault_index(tmp_path)
    pending = er.PendingStore()
    action = en.EnrichAction(
        action_type="pending_fact", item_id="first", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(
            date="2026-01-01", text="First fact.", tag="routine", claim_tag="",
            sources=["[[sources/a]]"]),
    )
    en.advance_planning_state([action], index, pending)
    assert er.resolve_entity("XPeng", index, pending).kind == "pending_second_mention"


def test_virtual_new_note_is_matched_and_clears_pending_fact(tmp_path):
    index = er.build_vault_index(tmp_path)
    pending = er.PendingStore(facts={
        "XPeng": [er.PendingFact(text="- 2026-01-01 — First fact. ([[sources/a]]) #routine")]
    })
    action = en.EnrichAction(
        action_type="new_note", item_id="second", entity="XPeng",
        target_note="companies/XPeng.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="name: XPeng\naliases: []\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="First fact.", tag="routine", claim_tag="",
                sources=["[[sources/a]]"])],
        ),
    )
    en.advance_planning_state([action], index, pending)
    resolution = er.resolve_entity("XPeng", index, pending)
    assert resolution.kind == "matched"
    assert resolution.note.rel == "companies/XPeng.md"
    assert not pending.has_entity("XPeng")


# --------------------------------------------------------------------------- hard guards

def test_timeline_entry_rejected_without_sources(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    bad = en.EnrichAction(
        action_type="timeline_entry", item_id="x", target_note="companies/Figure AI.md",
        timeline_entry=en.TimelineEntrySpec.model_construct(
            date="2026-01-01", text="Fact.", tag="routine", claim_tag="", sources=[]),
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
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), {"opinion-item"})
    assert accepted == []
    assert "opinion" in rejected[0].reason.lower()


def test_timeline_entry_rejected_for_unknown_target(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="timeline_entry", item_id="x", target_note="companies/Nonexistent.md",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "not found in vault index" in rejected[0].reason


def test_new_note_rejected_on_name_collision(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="new_note", item_id="x",
        target_note="companies/Figure.md",  # "Figure" is an existing alias
        new_note=en.NewNoteSpec(
            type="company", frontmatter_yaml="name: Figure\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Fact.", tag="routine", claim_tag="",
                sources=["[[sources/a]]"])]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "collision" in rejected[0].reason


def test_new_note_accepted_for_genuinely_new_name(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="new_note", item_id="x", entity="Apptronik",
        target_note="companies/Apptronik.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="type: company\nname: Apptronik\nsectors: [robotics]\n"
                             "watchlist: false\nstatus: active\n"
                             "created: 2026-01-01\nupdated: 2026-01-01\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Fact.", tag="routine", claim_tag="",
                sources=["[[sources/a]]"])]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert len(accepted) == 1
    assert rejected == []


def test_new_note_rejected_for_sector_outside_controlled_vocabulary(tmp_path):
    action = en.EnrichAction(
        action_type="new_note", item_id="x", entity="Apptronik",
        target_note="companies/Apptronik.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="type: company\nname: Apptronik\nstatus: active\n"
                             "sectors: [ai]\nwatchlist: false\n"
                             "created: 2026-01-01\nupdated: 2026-01-01\n",
            timeline_entries=[en.TimelineEntrySpec(
                date="2026-01-01", text="Fact.", tag="routine", claim_tag="",
                sources=["[[sources/a]]"])],
        ),
    )

    accepted, rejected = en.validate_actions(
        [action], er.build_vault_index(tmp_path), set(), set()
    )

    assert accepted == []
    assert "unknown-sector" in rejected[0].reason


def test_opinion_can_trigger_note_creation_using_only_prior_stored_fact(tmp_path):
    index = er.build_vault_index(tmp_path)
    entry = en.TimelineEntrySpec(
        date="2026-01-01", text="Prior fact.", tag="routine", claim_tag="",
        sources=["[[sources/a]]"],
    )
    action = en.EnrichAction(
        action_type="new_note", item_id="opinion", entity="Google",
        target_note="companies/Google.md",
        new_note=en.NewNoteSpec(
            type="company", frontmatter_yaml="type: company\nname: Google\naliases: []\n"
                                             "status: active\nsectors: [ai-applications]\n"
                                             "watchlist: false\ncreated: 2026-01-01\n"
                                             "updated: 2026-01-01\n",
            timeline_entries=[entry],
        ),
    )
    resolution_map = {
        "opinion": {
            lint_key("Google"): er.Resolution(
                kind="pending_second_mention",
                prior_facts=[er.PendingFact(text=en.format_timeline_line(entry))],
            )
        }
    }
    accepted, rejected = en.validate_actions(
        [action], index, set(), {"opinion"}, resolution_map=resolution_map
    )
    assert accepted == [action]
    assert rejected == []


def test_opinion_new_note_rejects_fact_from_opinion_itself(tmp_path):
    index = er.build_vault_index(tmp_path)
    prior = en.TimelineEntrySpec(
        date="2026-01-01", text="Prior fact.", tag="routine", claim_tag="",
        sources=["[[sources/a]]"],
    )
    opinion_fact = en.TimelineEntrySpec(
        date="2026-02-01", text="Opinion claim.", tag="routine", claim_tag="",
        sources=["[[sources/opinion]]"],
    )
    action = en.EnrichAction(
        action_type="new_note", item_id="opinion", entity="Google",
        target_note="companies/Google.md",
        new_note=en.NewNoteSpec(
            type="company", frontmatter_yaml="type: company\nname: Google\naliases: []\n"
                                             "status: active\nsectors: [ai-applications]\n"
                                             "watchlist: false\ncreated: 2026-01-01\n"
                                             "updated: 2026-01-01\n",
            timeline_entries=[prior, opinion_fact],
        ),
    )
    resolution_map = {
        "opinion": {
            lint_key("Google"): er.Resolution(
                kind="pending_second_mention",
                prior_facts=[er.PendingFact(text=en.format_timeline_line(prior))],
            )
        }
    }
    accepted, rejected = en.validate_actions(
        [action], index, set(), {"opinion"}, resolution_map=resolution_map
    )
    assert accepted == []
    assert "only verbatim timeline facts" in rejected[0].reason


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


def test_duplicate_action_is_rejected(tmp_path):
    action = en.EnrichAction(action_type="skip", item_id="x", reason="incidental")
    accepted, rejected = en.validate_actions([action, action], er.build_vault_index(tmp_path),
                                             set(), set())
    assert accepted == [action]
    assert rejected[0].reason == "duplicate action"


def test_frontmatter_patch_requires_supporting_accepted_timeline(tmp_path):
    figure_ai_note(tmp_path)
    action = en.EnrichAction(
        action_type="frontmatter_patch", item_id="x", target_note="companies/Figure AI.md",
        frontmatter_patch=en.FrontmatterPatchSpec(field="stage", value="series-c"),
    )
    accepted, rejected = en.validate_actions([action], er.build_vault_index(tmp_path), set(), set())
    assert accepted == []
    assert "no accepted timeline_entry" in rejected[0].reason


# --------------------------------------------------------------------------- pending_fact

def test_pending_fact_rejected_for_opinion_item(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="opinion-item", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), {"opinion-item"})
    assert accepted == []
    assert "opinion" in rejected[0].reason.lower()


def test_pending_fact_rejected_without_entity(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "missing entity" in rejected[0].reason


def test_pending_fact_rejected_when_entity_already_has_a_note(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="Figure AI",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "use timeline_entry" in rejected[0].reason


def test_pending_fact_rejected_without_sources(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec.model_construct(
            date="2026-01-01", text="Fact.", tag="routine", claim_tag="", sources=[]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert accepted == []
    assert "zero sources" in rejected[0].reason


def test_pending_fact_accepted_for_genuine_first_mention(tmp_path):
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, rejected = en.validate_actions([action], index, set(), set())
    assert len(accepted) == 1
    assert rejected == []


def test_pending_fact_resolution_must_be_first_mention(tmp_path):
    figure_ai_note(tmp_path)
    index = er.build_vault_index(tmp_path)
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="Figure AI",
        timeline_entry=en.TimelineEntrySpec(
            date="2026-01-01", text="Fact.", tag="routine", claim_tag="",
            sources=["[[sources/a]]"]),
    )
    resolution_map = {
        "x": {lint_key("Figure AI"): er.Resolution(kind="matched", note=index.by_name[
            lint_key("Figure AI")])}
    }
    accepted, rejected = en.validate_actions(
        [action], index, set(), set(), resolution_map=resolution_map
    )
    assert accepted == []
    assert "already resolves" in rejected[0].reason


def test_apply_pending_fact_appends_to_store(tmp_path):
    store = er.PendingStore()
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    en.apply_pending_fact(store, action)
    assert store.has_entity("XPeng")
    assert "Fact." in store.facts["XPeng"][0].text


def test_run_apply_persists_pending_fact_to_disk(tmp_path, monkeypatch):
    """Regression test for the gap this action type was added to close: a run must
    actually write a first-mention fact to meta/pending-entities.md, not just narrate it
    in a skip action's reason (which nothing ever persisted)."""
    input_path = make_input(tmp_path, [item(id="x", entities=["XPeng"])])
    index = er.build_vault_index(tmp_path)
    pending = er.PendingStore()

    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    accepted, _ = en.validate_actions([action], index, set(), set())
    for a in accepted:
        en.apply_action(a, pending)
    if any(a.action_type == "pending_fact" for a in accepted):
        er.save_pending_store(pending)

    assert er.PENDING_ENTITIES_PATH.exists()
    reloaded = er.load_pending_store()
    assert reloaded.has_entity("XPeng")
    assert "Fact." in reloaded.facts["XPeng"][0].text


def test_touched_paths_includes_pending_entities_file(tmp_path):
    action = en.EnrichAction(
        action_type="pending_fact", item_id="x", entity="XPeng",
        timeline_entry=en.TimelineEntrySpec(date="2026-01-01", text="Fact.", tag="routine",
                                            claim_tag="", sources=["[[sources/a]]"]),
    )
    paths = en.touched_paths([action])
    assert er.PENDING_ENTITIES_PATH in paths


# --------------------------------------------------------------------------- applying actions

def test_apply_timeline_entry_inserts_newest_first_under_year(tmp_path):
    path = figure_ai_note(tmp_path)
    entry_old = en.TimelineEntrySpec(date="2026-01-01", text="Older fact.", tag="routine",
                                     claim_tag="", sources=["[[sources/a]]"])
    entry_new = en.TimelineEntrySpec(date="2026-06-01", text="Newer fact.", tag="milestone",
                                     claim_tag="", sources=["[[sources/b]]"])
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
                                 claim_tag="", sources=["[[sources/a]]"])
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


def test_apply_frontmatter_patch_parses_structured_yaml_value(tmp_path):
    path = figure_ai_note(tmp_path)

    en.apply_frontmatter_patch(
        path, "last_round",
        '{type: series-c, amount_usd: 1000000000, lead: ["Parkway Venture Capital"]}',
    )

    import yaml, lint
    fm, _ = lint.split_frontmatter(path.read_text())
    data = yaml.safe_load(fm)
    assert data["last_round"]["amount_usd"] == 1000000000


def test_insert_timeline_bullet_orders_same_year_entries_by_date():
    body = "\n## Timeline\n\n### 2026\n\n## Funding history\n"
    dates = ["2026-10-07", "2026-10-09", "2026-10-05", "2026-10-12"]

    for date in dates:
        body = en.insert_timeline_bullet(body, f"- {date} — Fact.", date)

    positions = [body.index(date) for date in sorted(dates, reverse=True)]
    assert positions == sorted(positions)


def test_create_new_note_writes_frontmatter_and_timeline(tmp_path):
    action = en.EnrichAction(
        action_type="new_note", item_id="x",
        target_note="companies/Apptronik.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="name: Apptronik\nsectors: [robotics]\nwatchlist: false\nstatus: active\n",
            timeline_entries=[
                en.TimelineEntrySpec(date="2026-01-01", text="First fact.", tag="routine",
                                     claim_tag="", sources=["[[sources/a]]"]),
                en.TimelineEntrySpec(date="2026-02-01", text="Second fact.", tag="milestone",
                                     claim_tag="", sources=["[[sources/b]]"]),
            ]),
    )
    out_path = en.create_new_note(action)
    text = out_path.read_text()
    import yaml, lint
    fm, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm)
    assert data["name"] == "Apptronik"
    assert data["sectors"] == ["robotics"]
    import datetime as dt
    assert data["created"] == dt.date.today().isoformat()
    assert data["updated"] == dt.date.today().isoformat()
    assert "First fact." in body and "Second fact." in body
    # newest first
    assert body.index("Second fact.") < body.index("First fact.")
    assert "# Apptronik" in body
    assert "<note name>" not in body
    assert "### YYYY" not in body
    assert "\n-\n" not in body


def test_create_new_note_preserves_both_pending_and_new_facts(tmp_path):
    """Fact fidelity: a prior stored fact promoted into a new note must survive verbatim."""
    stored_text = ("- 2025-03-12 — XPeng planned up to $13.8B humanoid robot investment. "
                   "([[sources/xpeng]]) #routine #claim/reported")
    action = en.EnrichAction(
        action_type="new_note", item_id="x",
        target_note="companies/XPeng.md",
        new_note=en.NewNoteSpec(
            type="company",
            frontmatter_yaml="name: XPeng\nsectors: [robotics]\nwatchlist: false\nstatus: active\n",
            timeline_entries=[
                en.TimelineEntrySpec(date="2025-03-12", text="XPeng planned up to $13.8B humanoid "
                                     "robot investment.", tag="routine", claim_tag="claim/reported",
                                     sources=["[[sources/xpeng]]"]),
            ]),
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
