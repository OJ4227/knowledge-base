"""Tests for tools/triage.py against a mocked Anthropic client — no real API calls."""
import json

import pytest

import triage as tg


def make_raw_capture(tmp_path, slug, title="A title", source="sources/a", body="Some content."):
    path = tmp_path / "inbox" / f"{slug}--capture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
type: capture
---

# {title}

- source: [[{source}]]
- readwise_category: rss

## Excerpt

{body}
""",
        encoding="utf-8",
    )
    return path


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeMessage:
    def __init__(self, text):
        self.content = [FakeTextBlock(text)]


class FakeStream:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return FakeMessage(self._text)


class FakeMessages:
    def __init__(self, responder):
        self._responder = responder

    def stream(self, **kwargs):
        return FakeStream(self._responder(kwargs))


class FakeClient:
    def __init__(self, responder, api_key=None):
        self.messages = FakeMessages(responder)


def triage_response_json(items=None, dropped=None):
    return json.dumps({"dropped": dropped or [], "items": items or []})


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "ROOT", tmp_path)
    monkeypatch.setattr(tg, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(tg, "TRIAGE_DIR", tmp_path / "inbox" / "_triage")
    monkeypatch.setattr(tg, "PROMPT_PATH", tmp_path / "tools" / "prompts" / "triage.md")
    monkeypatch.setattr(tg, "TAXONOMY_PATH", tmp_path / "meta" / "taxonomy.md")
    monkeypatch.setattr(tg, "AGENT_INSTRUCTIONS_PATH",
                        tmp_path / "meta" / "agent-instructions.md")

    (tmp_path / "tools" / "prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "prompts" / "triage.md").write_text(
        "TAXONOMY:\n{taxonomy}\n\nRULES:\n{triage_rules}\n\nCAPTURES:\n{captures}\n",
        encoding="utf-8",
    )

    (tmp_path / "meta").mkdir(parents=True, exist_ok=True)
    (tmp_path / "meta" / "taxonomy.md").write_text(
        "# Taxonomy\n\n## Capture classification\n\nDomain stuff here.\n\n"
        "## Company sectors (`sectors:` field)\n\nirrelevant\n",
        encoding="utf-8",
    )
    (tmp_path / "meta" / "agent-instructions.md").write_text(
        "# Agent instructions\n\n"
        "### Triage (Stage 2, daily, one LLM context)\n\nTriage rule text here.\n\n"
        "### Enrich (Stage 3, daily, one LLM context)\n\nirrelevant\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return tmp_path


# --------------------------------------------------------------------------- prompt assembly

def test_load_taxonomy_extracts_capture_classification_section(tmp_path):
    text = tg.load_taxonomy()
    assert "Domain stuff here." in text
    assert "irrelevant" not in text


def test_load_triage_rules_extracts_only_triage_section(tmp_path):
    text = tg.load_triage_rules()
    assert "Triage rule text here." in text
    assert "irrelevant" not in text


def test_build_prompt_interpolates_all_placeholders(tmp_path):
    make_raw_capture(tmp_path, "2026-01-01-example")
    captures = tg.load_captures()
    prompt = tg.build_prompt(captures)
    assert "Domain stuff here." in prompt
    assert "Triage rule text here." in prompt
    assert "2026-01-01-example--capture.md" in prompt
    assert "Some content." in prompt


def test_build_prompt_survives_braces_in_capture_body(tmp_path):
    make_raw_capture(tmp_path, "2026-01-01-braces", body="A {weird} body with {braces}.")
    captures = tg.load_captures()
    prompt = tg.build_prompt(captures)
    assert "A {weird} body with {braces}." in prompt


# --------------------------------------------------------------------------- dry run

def test_dry_run_makes_no_api_call_and_writes_nothing(tmp_path, monkeypatch):
    make_raw_capture(tmp_path, "2026-01-01-example")

    def fail_if_called(*a, **k):
        raise AssertionError("API should not be called on --dry-run")

    monkeypatch.setattr(tg.anthropic, "Anthropic", fail_if_called)
    rc = tg.main(["--dry-run"])
    assert rc == 0
    assert not tg.TRIAGE_DIR.exists()
    assert (tmp_path / "inbox" / "2026-01-01-example--capture.md").exists()


def test_no_captures_is_a_clean_noop(tmp_path, monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("API should not be called with an empty inbox")

    monkeypatch.setattr(tg.anthropic, "Anthropic", fail_if_called)
    rc = tg.main([])
    assert rc == 0


# --------------------------------------------------------------------------- real run (mocked API)

def test_run_writes_result_and_clears_consumed_captures(tmp_path, monkeypatch):
    make_raw_capture(tmp_path, "2026-01-01-example", source="sources/example")

    response = triage_response_json(items=[{
        "id": "example-item",
        "title": "Example development",
        "summary": "Something happened.",
        "domains": ["ai"],
        "development_type": "product",
        "entities": ["Example Corp"],
        "concepts": [],
        "sources": ["[[sources/example]]"],
        "claim_status": "confirmed",
        "reason": None,
    }])

    monkeypatch.setattr(tg.anthropic, "Anthropic",
                        lambda api_key=None: FakeClient(lambda kwargs: response))

    rc = tg.main([])
    assert rc == 0

    out_files = list(tg.TRIAGE_DIR.glob("*.json"))
    assert len(out_files) == 1
    payload = json.loads(out_files[0].read_text())
    assert payload["items"][0]["title"] == "Example development"
    assert payload["captures_consumed"] == ["inbox/2026-01-01-example--capture.md"]

    assert not (tmp_path / "inbox" / "2026-01-01-example--capture.md").exists()


def test_run_records_dropped_captures_with_reason(tmp_path, monkeypatch):
    make_raw_capture(tmp_path, "2026-01-01-noise", title="Confirm your signup")

    response = triage_response_json(dropped=[{
        "capture": "inbox/2026-01-01-noise--capture.md",
        "reason": "signup confirmation, no event",
    }])
    monkeypatch.setattr(tg.anthropic, "Anthropic",
                        lambda api_key=None: FakeClient(lambda kwargs: response))

    rc = tg.main([])
    assert rc == 0

    out_files = list(tg.TRIAGE_DIR.glob("*.json"))
    payload = json.loads(out_files[0].read_text())
    assert payload["dropped"][0]["reason"] == "signup confirmation, no event"
    assert payload["items"] == []


def test_model_flag_is_passed_through(tmp_path, monkeypatch):
    make_raw_capture(tmp_path, "2026-01-01-example")
    seen = {}

    def responder(kwargs):
        seen["model"] = kwargs["model"]
        return triage_response_json()

    monkeypatch.setattr(tg.anthropic, "Anthropic",
                        lambda api_key=None: FakeClient(responder))

    rc = tg.main(["--model", "claude-haiku-4-5"])
    assert rc == 0
    assert seen["model"] == "claude-haiku-4-5"


def test_missing_api_key_fails_cleanly(tmp_path, monkeypatch):
    make_raw_capture(tmp_path, "2026-01-01-example")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = tg.main([])
    assert rc == 1
