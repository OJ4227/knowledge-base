"""Tests for tools/enrich_resolve.py — pure entity-resolution logic, no API calls."""
import pytest

import enrich_resolve as er


def write_note(tmp_path, rel, frontmatter, body="\n# Note\n"):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- vault index

def test_by_name_matches_on_name_and_alias(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: [Figure]')
    idx = er.build_vault_index(tmp_path)
    assert idx.by_name["figure ai"].rel == "companies/Figure AI.md"
    assert idx.by_name["figure"].rel == "companies/Figure AI.md"


def test_by_name_matches_on_stem_when_name_differs(tmp_path):
    write_note(tmp_path, "people/Brett Adcock.md", 'type: person\nname: "Brett Adcock"')
    idx = er.build_vault_index(tmp_path)
    assert idx.by_name["brett adcock"].rel == "people/Brett Adcock.md"


def test_unresolved_link_detected(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: []',
               body="\n## Competitors\n\n- [[Apptronik]]\n")
    idx = er.build_vault_index(tmp_path)
    assert "apptronik" in idx.unresolved_link_targets


def test_resolved_link_not_in_unresolved_set(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: []',
               body="\n[[Brett Adcock]]\n")
    write_note(tmp_path, "people/Brett Adcock.md", 'type: person\nname: "Brett Adcock"')
    idx = er.build_vault_index(tmp_path)
    assert "brett adcock" not in idx.unresolved_link_targets


# --------------------------------------------------------------------------- pending store

def test_pending_store_round_trips_fact_text_exactly(tmp_path):
    path = tmp_path / "pending-entities.md"
    store = er.PendingStore()
    fact_text = ("- 2025-03-12 — XPeng planned up to $13.8B humanoid robot investment. "
                 "([[sources/xpeng]]) #routine #claim/reported")
    store.facts["XPeng"] = [er.PendingFact(text=fact_text)]

    er.save_pending_store(store, path)
    loaded = er.load_pending_store(path)

    assert loaded.facts["XPeng"][0].text == fact_text


def test_pending_store_missing_file_is_empty(tmp_path):
    store = er.load_pending_store(tmp_path / "does-not-exist.md")
    assert store.facts == {}


def test_pending_store_multiple_entities_and_facts(tmp_path):
    path = tmp_path / "pending-entities.md"
    store = er.PendingStore()
    store.facts["XPeng"] = [
        er.PendingFact(text="- 2025-03-12 — First fact. ([[sources/a]]) #routine"),
        er.PendingFact(text="- 2025-04-01 — Second fact. ([[sources/b]]) #milestone"),
    ]
    store.facts["Amazon"] = [
        er.PendingFact(text="- 2025-05-18 — Vulcan robot demoed. ([[sources/c]]) #routine"),
    ]
    er.save_pending_store(store, path)
    loaded = er.load_pending_store(path)

    assert len(loaded.facts["XPeng"]) == 2
    assert loaded.facts["XPeng"][0].text.endswith("#routine")
    assert loaded.facts["XPeng"][1].text.endswith("#milestone")
    assert len(loaded.facts["Amazon"]) == 1


# --------------------------------------------------------------------------- resolve_entity

def test_resolve_entity_matched(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: [Figure]')
    idx = er.build_vault_index(tmp_path)
    pending = er.PendingStore()

    result = er.resolve_entity("Figure AI", idx, pending)
    assert result.kind == "matched"
    assert result.note.rel == "companies/Figure AI.md"

    result_alias = er.resolve_entity("Figure", idx, pending)
    assert result_alias.kind == "matched"


def test_resolve_entity_pending_second_mention_via_unresolved_link(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: []',
               body="\n## Competitors\n\n- [[Apptronik]]\n")
    idx = er.build_vault_index(tmp_path)
    pending = er.PendingStore()

    result = er.resolve_entity("Apptronik", idx, pending)
    assert result.kind == "pending_second_mention"
    assert result.prior_facts == []


def test_resolve_entity_pending_second_mention_via_prior_stored_fact(tmp_path):
    idx = er.build_vault_index(tmp_path)
    pending = er.PendingStore()
    pending.facts["XPeng"] = [er.PendingFact(text="- 2025-03-12 — First fact. ([[sources/a]]) #routine")]

    result = er.resolve_entity("XPeng", idx, pending)
    assert result.kind == "pending_second_mention"
    assert len(result.prior_facts) == 1
    assert result.prior_facts[0].text == "- 2025-03-12 — First fact. ([[sources/a]]) #routine"


def test_resolve_entity_pending_first_mention(tmp_path):
    idx = er.build_vault_index(tmp_path)
    pending = er.PendingStore()

    result = er.resolve_entity("XPeng", idx, pending)
    assert result.kind == "pending_first_mention"
    assert result.prior_facts == []


def test_resolve_entity_case_insensitive(tmp_path):
    write_note(tmp_path, "companies/Figure AI.md",
               'type: company\nname: "Figure AI"\naliases: []')
    idx = er.build_vault_index(tmp_path)
    pending = er.PendingStore()

    result = er.resolve_entity("figure ai", idx, pending)
    assert result.kind == "matched"
