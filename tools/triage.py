#!/usr/bin/env python3
"""Stage 2 pipeline step: Triage.

Reads every raw capture in `inbox/`, fans each newsletter-style capture out into its
component developments, dedupes across captures, classifies on the taxonomy
(`meta/taxonomy.md`), and writes one run file to `inbox/_triage/`. Consumed raw captures
are deleted. See `DESIGN.md` §7 and `meta/agent-instructions.md` for how this fits the
pipeline.

Usage:
    python tools/triage.py                           # real run
    python tools/triage.py --dry-run                 # print the assembled prompt, call nothing
    python tools/triage.py --model claude-haiku-4-5   # override the model (default: claude-sonnet-5)

Requires one of, in the environment (source tools/.env first):
  - ANTHROPIC_API_KEY                         — direct Anthropic API
  - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN — a gateway/proxy in front of the API
    (e.g. a corporate relay) that speaks Bearer auth instead of an Anthropic key
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = ROOT / "inbox"
TRIAGE_DIR = INBOX_DIR / "_triage"
PROMPT_PATH = ROOT / "tools" / "prompts" / "triage.md"
TAXONOMY_PATH = ROOT / "meta" / "taxonomy.md"
AGENT_INSTRUCTIONS_PATH = ROOT / "meta" / "agent-instructions.md"

DEFAULT_MODEL = "claude-sonnet-5"
DOMAINS = ("ai", "robotics", "hardware/compute", "business")
DEVELOPMENT_TYPES = (
    "model-release", "research", "capability-demo", "product", "hardware", "benchmark",
    "open-source", "funding", "m&a", "people-move", "shutdown", "policy", "opinion",
)
CLAIM_STATUSES = ("confirmed", "reported", "rumored", "disputed")


# --------------------------------------------------------------------------- schema

class DroppedCapture(BaseModel):
    capture: str
    reason: str


class TriageItem(BaseModel):
    id: str
    title: str
    summary: str
    domains: list[Literal[DOMAINS]]
    development_type: Literal[DEVELOPMENT_TYPES]
    entities: list[str]
    concepts: list[str]
    sources: list[str]
    claim_status: Literal[CLAIM_STATUSES]
    reason: str | None = None


class TriageResult(BaseModel):
    dropped: list[DroppedCapture]
    items: list[TriageItem]


# --------------------------------------------------------------------------- captures

@dataclass
class Capture:
    path: Path
    rel: str
    body: str


def load_captures() -> list[Capture]:
    if not INBOX_DIR.exists():
        return []
    captures = []
    for path in sorted(INBOX_DIR.glob("*--capture.md")):
        rel = str(path.relative_to(ROOT))
        captures.append(Capture(path=path, rel=rel, body=path.read_text(encoding="utf-8")))
    return captures


def render_captures_block(captures: list[Capture]) -> str:
    parts = []
    for cap in captures:
        parts.append(f"### {cap.rel}\n\n{cap.body.strip()}\n")
    return "\n".join(parts)


# --------------------------------------------------------------------------- prompt assembly

def section_between(text: str, start_heading: str, end_heading: str | None) -> str:
    start = text.index(start_heading) + len(start_heading)
    end = text.index(end_heading, start) if end_heading else len(text)
    return text[start:end].strip()


def load_taxonomy() -> str:
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    return section_between(text, "## Capture classification", "## Company sectors")


def load_triage_rules() -> str:
    text = AGENT_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    return section_between(text, "### Triage (Stage 2, daily, one LLM context)",
                            "### Enrich (Stage 3, daily, one LLM context)")


def build_prompt(captures: list[Capture]) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        taxonomy=load_taxonomy(),
        triage_rules=load_triage_rules(),
        captures=render_captures_block(captures),
    )


# --------------------------------------------------------------------------- client

def build_client() -> anthropic.Anthropic | None:
    """Resolve credentials the same way Claude Code itself does: a gateway/proxy
    (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN, Bearer auth) takes priority over a direct
    Anthropic API key, since a gateway is the deliberate choice when both are configured.
    Returns None if neither is set.
    """
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if base_url and auth_token:
        return anthropic.Anthropic(base_url=base_url, auth_token=auth_token)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return anthropic.Anthropic(api_key=api_key)

    return None


# --------------------------------------------------------------------------- output writers

def write_result(result: TriageResult, run_date: str, consumed: list[str]) -> Path:
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRIAGE_DIR / f"{run_date}.json"
    payload = {
        "run_date": run_date,
        "captures_consumed": consumed,
        "dropped": [d.model_dump() for d in result.dropped],
        "items": [i.model_dump() for i in result.items],
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- main

def run(dry_run: bool, model: str) -> int:
    captures = load_captures()
    if not captures:
        print("inbox/ has no raw captures — nothing to triage")
        return 0

    prompt = build_prompt(captures)
    print(f"assembled prompt for {len(captures)} capture(s), model={model}")

    if dry_run:
        print("\n--- dry run: prompt below, no API call made ---\n")
        print(prompt)
        return 0

    client = build_client()
    if client is None:
        print("No credentials found. Set ANTHROPIC_API_KEY, or ANTHROPIC_BASE_URL + "
              "ANTHROPIC_AUTH_TOKEN for a gateway. Source tools/.env first.",
              file=sys.stderr)
        return 1

    with client.messages.stream(
        model=model,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": prompt,
                         "cache_control": {"type": "ephemeral"}}],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": TriageResult.model_json_schema(),
            },
        },
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    result = TriageResult.model_validate_json(text)

    run_date = dt.date.today().isoformat()
    consumed = [c.rel for c in captures]
    out_path = write_result(result, run_date, consumed)

    for cap in captures:
        cap.path.unlink()

    print(f"wrote {out_path.relative_to(ROOT)}: {len(result.items)} item(s), "
          f"{len(result.dropped)} dropped; removed {len(captures)} raw capture(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the assembled prompt, make no API call")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"model to use (default: {DEFAULT_MODEL})")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run, model=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
