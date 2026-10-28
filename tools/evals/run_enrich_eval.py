#!/usr/bin/env python3
"""Scored eval for the Enrich prompt (tools/prompts/enrich.md + tools/enrich.py).

THIS SCRIPT COSTS REAL MONEY ON EVERY RUN — it calls the Anthropic API once per
invocation. Never invoked by pytest or the pre-commit hook.

Runs Enrich once over the union of every golden case's items (selected from a real Triage
output file by item id), scores each case's deterministic structural checks against the
model's *accepted* actions (after the same hard-guard validation `enrich.py --apply` would
run — rejected actions never count toward a case), and prints a per-case pass/fail table
plus token counts and estimated cost. Runs against the real vault index, read-only — no
file is ever written by this script, regardless of what the model proposes.

Usage:
    python tools/evals/run_enrich_eval.py
    python tools/evals/run_enrich_eval.py --input inbox/_triage/2026-10-27.json
    python tools/evals/run_enrich_eval.py --model claude-sonnet-5
    python tools/evals/run_enrich_eval.py --case figure-series-c-existing-note

Requires one of, in the environment (source tools/.env first):
  - ANTHROPIC_API_KEY                         — direct Anthropic API
  - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN — a gateway/proxy in front of the API
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import enrich as en
import enrich_resolve as er
import lint

CASES_DIR = Path(__file__).resolve().parent / "cases" / "enrich"
DEFAULT_INPUT = en.ROOT / "inbox" / "_triage" / "2026-10-27.json"

MODEL_PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
}


# --------------------------------------------------------------------------- case loading

def load_cases(names: list[str] | None) -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        if names and path.stem not in names:
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        case["name"] = path.stem
        cases.append(case)
    return cases


def union_item_ids(cases: list[dict]) -> list[str]:
    seen: list[str] = []
    for case in cases:
        for item_id in case["item_ids"]:
            if item_id not in seen:
                seen.append(item_id)
    return seen


# --------------------------------------------------------------------------- running enrich

def run_enrich_over(item_ids: list[str], input_path: Path, model: str,
                     effort: str = en.tg.DEFAULT_EFFORT):
    all_items = en.load_triage_items(input_path)
    by_id = {i.id: i for i in all_items}
    missing = [i for i in item_ids if i not in by_id]
    if missing:
        print(f"item id(s) not found in {input_path}: {missing}", file=sys.stderr)
        raise SystemExit(1)
    items = [by_id[i] for i in item_ids]

    index = er.build_vault_index(en.ROOT)
    pending = er.load_pending_store()
    prompt = en.build_prompt(items, index, pending)

    client = en.tg.build_client()
    if client is None:
        print("No credentials found. Set ANTHROPIC_API_KEY, or ANTHROPIC_BASE_URL + "
              "ANTHROPIC_AUTH_TOKEN for a gateway. Source tools/.env first.",
              file=sys.stderr)
        raise SystemExit(1)

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
            "effort": effort,
            "format": {"type": "json_schema", "schema": en.EnrichResult.model_json_schema()},
        },
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    result = en.EnrichResult.model_validate_json(text)

    rejected_pairs = en.load_rejected_pairs()
    opinion_ids = {i.id for i in items if i.development_type == "opinion"}
    accepted, rejected = en.validate_actions(result.actions, index, rejected_pairs, opinion_ids)

    return accepted, rejected, response.usage


# --------------------------------------------------------------------------- scoring

def _note_stem(path: str | None) -> str | None:
    return Path(path).stem if path else None


def _action_matches(a: en.EnrichAction, check: dict) -> bool:
    if "action_type" in check and a.action_type != check["action_type"]:
        return False
    if "target_note" in check and a.target_note != check["target_note"]:
        return False
    if "target_note_stem" in check:
        # "the note this action is about" — target_note for most action types, but
        # new_note_path for a new_note action (it has no target_note at all)
        stem = _note_stem(a.target_note) or _note_stem(a.new_note_path)
        if stem != check["target_note_stem"]:
            return False
    if "new_note_type" in check and a.new_note_type != check["new_note_type"]:
        return False
    if "new_note_path_stem" in check and _note_stem(a.new_note_path) != check["new_note_path_stem"]:
        return False
    if "frontmatter_field" in check and a.frontmatter_field != check["frontmatter_field"]:
        return False
    if "sources_include" in check:
        sources = a.timeline_entry.sources if a.timeline_entry else []
        if not all(s in sources for s in check["sources_include"]):
            return False
    return True


def check_item_has_action(case: dict, check: dict, actions: list[en.EnrichAction]) -> tuple[bool, str]:
    item_actions = [a for a in actions if a.item_id == check["item_id"]]
    hit = any(_action_matches(a, check) for a in item_actions)
    return hit, ("matching action found" if hit
                 else f"no action for item {check['item_id']!r} matched {check}")


def check_item_lacks_action(case: dict, check: dict, actions: list[en.EnrichAction]) -> tuple[bool, str]:
    item_actions = [a for a in actions if a.item_id == check["item_id"]]
    hit = any(_action_matches(a, check) for a in item_actions)
    return not hit, (f"unexpectedly found a matching action for item {check['item_id']!r}: {check}"
                      if hit else f"no action matched {check}, as expected")


CHECKS = {
    "item_has_action": check_item_has_action,
    "item_lacks_action": check_item_lacks_action,
}


def score_case(case: dict, actions: list[en.EnrichAction]) -> list[tuple[str, bool, str]]:
    out = []
    for check in case["checks"]:
        fn = CHECKS[check["type"]]
        ok, detail = fn(case, check, actions)
        out.append((check["type"], ok, detail))
    return out


# --------------------------------------------------------------------------- reporting

def estimate_cost(model: str, usage) -> float | None:
    prices = MODEL_PRICES.get(model)
    if not prices:
        return None
    in_price, out_price = prices
    input_tokens = getattr(usage, "input_tokens", 0) + getattr(usage, "cache_creation_input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    return (input_tokens / 1_000_000 * in_price) + (output_tokens / 1_000_000 * out_price)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"Triage output file to pull items from (default: {DEFAULT_INPUT})")
    parser.add_argument("--model", default=en.tg.DEFAULT_MODEL)
    parser.add_argument("--effort", default=en.tg.DEFAULT_EFFORT,
                        choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--case", action="append", dest="cases",
                        help="run only this case (repeatable); default: all cases")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        print("no matching cases found", file=sys.stderr)
        return 1

    item_ids = union_item_ids(cases)
    print(f"running enrich over {len(item_ids)} item(s) from {len(cases)} case(s), "
          f"model={args.model}, effort={args.effort}, input={args.input}\n")

    accepted, rejected, usage = run_enrich_over(item_ids, args.input, args.model, args.effort)

    if rejected:
        print(f"{len(rejected)} action(s) rejected by hard guards (never count toward scoring):")
        for r in rejected:
            print(f"  [REJECTED] {en.describe_action(r.action)} — {r.reason}")
        print()

    total_checks = 0
    total_passed = 0
    for case in cases:
        print(f"## {case['name']}")
        for check_type, ok, detail in score_case(case, accepted):
            total_checks += 1
            total_passed += ok
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {check_type}: {detail}")

        for a in accepted:
            if a.item_id in case["item_ids"]:
                print(f"    - {en.describe_action(a)}")
        print()

    print(f"score: {total_passed}/{total_checks}")
    print(f"tokens: input={usage.input_tokens} output={usage.output_tokens} "
          f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)}")
    cost = estimate_cost(args.model, usage)
    if cost is not None:
        print(f"estimated cost: ${cost:.4f}")

    return 0 if total_passed == total_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
