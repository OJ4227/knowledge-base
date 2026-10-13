"""Tests for tools/collect_readwise.py against a mocked Readwise API — no real network calls."""
import json

import pytest

import collect_readwise as cr


def doc(id, title="A title", category="rss", html="<p>Some content. More content.</p>",
        published_date="2026-01-01", updated_at="2026-01-01T00:00:00+00:00",
        parent_id=None, source_url="https://example.com/a", site_name="Example",
        author=None):
    return {
        "id": id,
        "title": title,
        "category": category,
        "html_content": html,
        "published_date": published_date,
        "created_at": updated_at,
        "updated_at": updated_at,
        "parent_id": parent_id,
        "source_url": source_url,
        "site_name": site_name,
        "author": author,
    }


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 429:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "ROOT", tmp_path)
    monkeypatch.setattr(cr, "STATE_PATH", tmp_path / "meta" / "collector-state.json")
    monkeypatch.setattr(cr, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(cr, "SNAPSHOTS_DIR", tmp_path / "sources" / "_snapshots")
    monkeypatch.setattr(cr, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setenv("READWISE_TOKEN", "test-token")
    (tmp_path / "meta").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_single_page_writes_source_and_inbox(tmp_path, monkeypatch):
    payload = {"count": 1, "nextPageCursor": None, "results": [doc("abc123")]}
    monkeypatch.setattr(cr.requests, "get", lambda *a, **k: FakeResponse(payload))

    rc = cr.main([])
    assert rc == 0

    sources = list((tmp_path / "sources").glob("*.md"))
    assert len(sources) == 1
    assert "readwise_id: abc123" in sources[0].read_text()

    inbox = list((tmp_path / "inbox").glob("*.md"))
    assert len(inbox) == 1

    snapshots = list((tmp_path / "sources" / "_snapshots").glob("*.html"))
    assert len(snapshots) == 1


def test_pagination_follows_cursor(tmp_path, monkeypatch):
    page1 = {"count": 2, "nextPageCursor": "cursor-2", "results": [doc("a")]}
    page2 = {"count": 2, "nextPageCursor": None, "results": [doc("b")]}
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return FakeResponse(page1 if calls["n"] == 1 else page2)

    monkeypatch.setattr(cr.requests, "get", fake_get)
    rc = cr.main([])
    assert rc == 0
    assert calls["n"] == 2
    assert len(list((tmp_path / "sources").glob("*.md"))) == 2


def test_highlights_are_skipped(tmp_path, monkeypatch):
    payload = {"count": 2, "nextPageCursor": None,
               "results": [doc("parent1"), doc("child1", parent_id="parent1")]}
    monkeypatch.setattr(cr.requests, "get", lambda *a, **k: FakeResponse(payload))
    rc = cr.main([])
    assert rc == 0
    assert len(list((tmp_path / "sources").glob("*.md"))) == 1


def test_rerun_is_idempotent(tmp_path, monkeypatch):
    payload = {"count": 1, "nextPageCursor": None, "results": [doc("abc123")]}
    monkeypatch.setattr(cr.requests, "get", lambda *a, **k: FakeResponse(payload))

    assert cr.main([]) == 0
    assert cr.main([]) == 0  # same document, same id — should not duplicate

    assert len(list((tmp_path / "sources").glob("*.md"))) == 1
    assert len(list((tmp_path / "inbox").glob("*.md"))) == 1


def test_watermark_persists_and_is_sent_on_next_run(tmp_path, monkeypatch):
    payload = {"count": 1, "nextPageCursor": None,
               "results": [doc("abc123", updated_at="2026-03-01T00:00:00+00:00")]}
    seen_params = []

    def fake_get(*a, **k):
        seen_params.append(k.get("params", {}))
        return FakeResponse(payload)

    monkeypatch.setattr(cr.requests, "get", fake_get)
    assert cr.main([]) == 0

    state = json.loads(cr.STATE_PATH.read_text())
    assert state["readwise"]["last_run_utc"] == "2026-03-01T00:00:00+00:00"

    assert cr.main([]) == 0
    assert seen_params[-1]["updatedAfter"] == "2026-03-01T00:00:00+00:00"


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    payload = {"count": 1, "nextPageCursor": None, "results": [doc("abc123")]}
    monkeypatch.setattr(cr.requests, "get", lambda *a, **k: FakeResponse(payload))

    rc = cr.main(["--dry-run"])
    assert rc == 0
    assert not (tmp_path / "sources").exists() or \
        not list((tmp_path / "sources").glob("*.md"))
    assert not cr.STATE_PATH.exists()


def test_slug_collision_gets_suffixed(tmp_path, monkeypatch):
    payload = {"count": 2, "nextPageCursor": None,
               "results": [doc("a", title="Same Title", published_date="2026-01-01"),
                           doc("b", title="Same Title", published_date="2026-01-01")]}
    monkeypatch.setattr(cr.requests, "get", lambda *a, **k: FakeResponse(payload))
    rc = cr.main([])
    assert rc == 0
    names = sorted(p.stem for p in (tmp_path / "sources").glob("*.md"))
    assert names == ["2026-01-01-same-title", "2026-01-01-same-title-2"]


def test_missing_token_fails_cleanly(monkeypatch):
    monkeypatch.delenv("READWISE_TOKEN", raising=False)
    rc = cr.main([])
    assert rc == 1


def test_rate_limit_retry(tmp_path, monkeypatch):
    payload = {"count": 1, "nextPageCursor": None, "results": [doc("abc123")]}
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse({}, status_code=429, headers={"Retry-After": "0"})
        return FakeResponse(payload)

    monkeypatch.setattr(cr.requests, "get", fake_get)
    monkeypatch.setattr(cr.time, "sleep", lambda s: None)
    rc = cr.main([])
    assert rc == 0
    assert calls["n"] == 2
