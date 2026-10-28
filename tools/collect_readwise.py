#!/usr/bin/env python3
"""Stage 1 collector: Readwise Reader (RSS feeds + email newsletters).

Fetches documents added/updated since the last run, writes a `sources/` note + local
snapshot per item, and a raw capture into `inbox/`. See `DESIGN.md` §7 and
`meta/agent-instructions/collectors.md` for how this fits the pipeline.

Usage:
    python tools/collect_readwise.py              # real run
    python tools/collect_readwise.py --dry-run    # report what would be written, write nothing

Requires READWISE_TOKEN in the environment (source tools/.env first).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import requests

API_BASE = "https://readwise.io/api/v3"
LIST_URL = f"{API_BASE}/list/"
RATE_LIMIT_SLEEP_DEFAULT = 60
PAGE_LIMIT = 100

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "meta" / "collector-state.json"
SOURCES_DIR = ROOT / "sources"
SNAPSHOTS_DIR = SOURCES_DIR / "_snapshots"
INBOX_DIR = ROOT / "inbox"

COLLECTOR_KEY = "readwise"
EXCERPT_WORD_LIMIT = 500
FIRST_RUN_WINDOW_DAYS = 7  # on a fresh vault, don't sweep in pre-existing unrelated history


# --------------------------------------------------------------------------- HTML -> text

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.parts)).strip()


def html_to_text(html: str) -> str:
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def first_sentences(text: str, count: int = 3) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:count]).strip()


def truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + " [...]"


# --------------------------------------------------------------------------- slug

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = _SLUG_STRIP_RE.sub("-", title.lower()).strip("-")
    return slug[:80] or "untitled"


def unique_slug(date: str, base_slug: str, existing: set[str]) -> str:
    candidate = f"{date}-{base_slug}"
    if candidate not in existing:
        return candidate
    n = 2
    while f"{candidate}-{n}" in existing:
        n += 1
    return f"{candidate}-{n}"


# --------------------------------------------------------------------------- state

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_watermark(state: dict) -> str | None:
    return state.get(COLLECTOR_KEY, {}).get("last_run_utc")


def set_watermark(state: dict, value: str) -> dict:
    state = dict(state)
    state[COLLECTOR_KEY] = {"last_run_utc": value}
    return state


# --------------------------------------------------------------------------- readwise API

@dataclass
class Document:
    id: str
    title: str
    author: str | None
    source_url: str | None
    category: str | None
    site_name: str | None
    published_date: str | None
    created_at: str | None
    updated_at: str | None
    parent_id: str | None
    html_content: str | None

    @classmethod
    def from_api(cls, data: dict) -> "Document":
        return cls(
            id=data["id"],
            title=data.get("title") or "Untitled",
            author=data.get("author"),
            source_url=data.get("source_url"),
            category=data.get("category"),
            site_name=data.get("site_name"),
            published_date=data.get("published_date"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            parent_id=data.get("parent_id"),
            html_content=data.get("html_content"),
        )


def fetch_documents(token: str, updated_after: str | None) -> list[Document]:
    headers = {"Authorization": f"Token {token}"}
    documents: list[Document] = []
    cursor: str | None = None

    while True:
        params = {"withHtmlContent": "true", "limit": str(PAGE_LIMIT)}
        if updated_after:
            params["updatedAfter"] = updated_after
        if cursor:
            params["pageCursor"] = cursor

        resp = requests.get(LIST_URL, headers=headers, params=params, timeout=30)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", RATE_LIMIT_SLEEP_DEFAULT))
            print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue

        resp.raise_for_status()
        data = resp.json()

        for raw in data.get("results", []):
            doc = Document.from_api(raw)
            if doc.parent_id:
                continue  # highlight/note on a parent document, not a top-level capture
            documents.append(doc)

        cursor = data.get("nextPageCursor")
        if not cursor:
            break

    return documents


# --------------------------------------------------------------------------- writers

def render_source_note(doc: Document, date: str, extract: str, local_copy_rel: str) -> str:
    title = doc.title.replace('"', '\\"')
    publication = (doc.site_name or doc.author or "").replace('"', '\\"')
    authors = f'["{doc.author}"]' if doc.author else "[]"
    published = doc.published_date or date
    accessed = dt.date.today().isoformat()
    url = doc.source_url or ""

    frontmatter = f"""---
type: source
title: "{title}"
publication: "{publication}"
authors: {authors}
published: {published}
accessed: {accessed}
url: "{url}"
archive_url: ""
local_copy: "{local_copy_rel}"
tier: tertiary
superseded_by:
---
<!-- readwise_id: {doc.id} -->

# {title}

<!-- IMMUTABLE once written. Corrections = a new source note + superseded_by on this one. -->

## Extract

> {extract}

## Claims drawn from this source

"""
    return frontmatter


def render_inbox_capture(doc: Document, sources_link: str, excerpt: str) -> str:
    title = doc.title.replace('"', '\\"')
    return f"""---
type: capture
---

# {title}

- source: [[{sources_link}]]
- readwise_category: {doc.category or "unknown"}

## Excerpt

{excerpt}
"""


def existing_readwise_ids() -> set[str]:
    ids: set[str] = set()
    pattern = re.compile(r"<!--\s*readwise_id:\s*([^\s]+?)\s*-->")
    if not SOURCES_DIR.exists():
        return ids
    for path in SOURCES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        m = pattern.search(text)
        if m:
            ids.add(m.group(1))
    return ids


def existing_slugs() -> set[str]:
    if not SOURCES_DIR.exists():
        return set()
    return {p.stem for p in SOURCES_DIR.glob("*.md")}


# --------------------------------------------------------------------------- main

def run(dry_run: bool) -> int:
    token = os.environ.get("READWISE_TOKEN")
    if not token:
        print("READWISE_TOKEN is not set in the environment. Source tools/.env first.",
              file=sys.stderr)
        return 1

    state = load_state()
    watermark = get_watermark(state)
    if watermark is None:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=FIRST_RUN_WINDOW_DAYS)
        fetch_after = cutoff.isoformat()
        print(f"watermark: (none — first run, bounding to last {FIRST_RUN_WINDOW_DAYS} days)")
    else:
        fetch_after = watermark
        print(f"watermark: {watermark}")

    documents = fetch_documents(token, fetch_after)
    print(f"fetched {len(documents)} top-level document(s) since {fetch_after}")

    known_ids = existing_readwise_ids()
    slugs_in_use = existing_slugs()

    new_watermark = watermark
    written = 0

    for doc in documents:
        if doc.updated_at and (new_watermark is None or doc.updated_at > new_watermark):
            new_watermark = doc.updated_at

        if doc.id in known_ids:
            continue  # idempotency: already captured in a prior run

        date = (doc.published_date or (doc.created_at or "")[:10]
                or dt.date.today().isoformat())
        base_slug = slugify(doc.title)
        slug = unique_slug(date, base_slug, slugs_in_use)
        slugs_in_use.add(slug)

        text = html_to_text(doc.html_content or "")
        extract = first_sentences(text) or "(no extract available)"
        excerpt = truncate_words(text, EXCERPT_WORD_LIMIT) or "(no content available)"

        source_rel = f"sources/{slug}"
        snapshot_rel = f"sources/_snapshots/{slug}.html"
        inbox_slug = f"{slug}--capture"  # distinct stem from the source note it links to
        inbox_rel = f"inbox/{inbox_slug}.md"

        print(f"  + {source_rel}  ({doc.category}, {doc.title[:60]!r})")

        if not dry_run:
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            INBOX_DIR.mkdir(parents=True, exist_ok=True)

            (SNAPSHOTS_DIR / f"{slug}.html").write_text(doc.html_content or "",
                                                         encoding="utf-8")
            (SOURCES_DIR / f"{slug}.md").write_text(
                render_source_note(doc, date, extract, snapshot_rel), encoding="utf-8")
            (INBOX_DIR / f"{inbox_slug}.md").write_text(
                render_inbox_capture(doc, source_rel, excerpt), encoding="utf-8")

        written += 1

    if dry_run:
        print(f"\ndry run: would write {written} new source(s); watermark would advance to "
              f"{new_watermark or '(unchanged)'}")
        return 0

    if new_watermark and new_watermark != watermark:
        save_state(set_watermark(state, new_watermark))

    print(f"\nwrote {written} new source(s); watermark now {new_watermark or '(unchanged)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written, write nothing")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
