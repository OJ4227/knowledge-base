#!/usr/bin/env python3
"""Scored eval for the Triage prompt (tools/prompts/triage.md + tools/triage.py).

THIS SCRIPT COSTS REAL MONEY ON EVERY RUN — it calls the Anthropic API once per
invocation. Never invoked by pytest or the pre-commit hook.

Runs Triage once over the union of every golden case's input captures (never against the
live inbox/), scores each case's deterministic checks against the result, and prints a
per-case pass/fail table plus token counts and estimated cost. Use --model to compare
models on the same prompt and corpus:

Usage:
    python tools/evals/run_eval.py
    python tools/evals/run_eval.py --model claude-haiku-4-5
    python tools/evals/run_eval.py --case dup-easy-oxide --case fanout-oxide-hardware

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

import triage as tg

CASES_DIR = Path(__file__).resolve().parent / "cases" / "triage"

# $/MTok (input, output) — kept here rather than queried live, since this is a planning
# estimate, not a billing record. Update when pricing changes.
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


def union_inputs(cases: list[dict]) -> list[str]:
    seen: list[str] = []
    for case in cases:
        for rel in case["inputs"]:
            if rel not in seen:
                seen.append(rel)
    return seen


# --------------------------------------------------------------------------- running triage

def run_triage_over(rel_paths: list[str], model: str) -> tuple[tg.TriageResult, object]:
    captures = [tg.Capture(path=tg.ROOT / rel, rel=rel,
                            body=(tg.ROOT / rel).read_text(encoding="utf-8"))
                for rel in rel_paths]
    prompt = tg.build_prompt(captures)

    client = tg.build_client()
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
            "format": {"type": "json_schema", "schema": tg.TriageResult.model_json_schema()},
        },
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    return tg.TriageResult.model_validate_json(text), response.usage


# --------------------------------------------------------------------------- scoring

def items_from_inputs(result: tg.TriageResult, rel_paths: list[str]) -> list[tg.TriageItem]:
    link_slugs = {rel.split("/")[-1].removesuffix("--capture.md") for rel in rel_paths}
    out = []
    for item in result.items:
        for src in item.sources:
            # [[sources/<slug>]] -> <slug>
            slug = src.strip("[]").split("/", 1)[-1]
            if slug in link_slugs:
                out.append(item)
                break
    return out


def dropped_rels(result: tg.TriageResult) -> set[str]:
    return {d.capture for d in result.dropped}


def check_all_dropped(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    missing = [rel for rel in case["inputs"] if rel not in dropped_rels(result)]
    if missing:
        return False, f"not dropped: {missing}"
    return True, "all inputs dropped"


def check_none_become_items(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    if matches:
        return False, f"{len(matches)} item(s) unexpectedly derived from these inputs"
    return True, "no items derived from these inputs"


def check_no_item_development_type(case: dict, check: dict,
                                    result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    bad = [i for i in matches if i.development_type == check["development_type"]]
    if bad:
        return False, f"found item(s) with development_type={check['development_type']}"
    return True, "no matching item has that development_type"


def _item_matches(item: tg.TriageItem, check: dict) -> bool:
    if "title_contains" in check and check["title_contains"].lower() not in item.title.lower():
        return False
    if "entities_include" in check:
        have = {e.lower() for e in item.entities}
        for want in check["entities_include"]:
            if want.lower() not in have and not any(want.lower() in h for h in have):
                return False
    if "domains_include" in check:
        have = set(item.domains)
        if not set(check["domains_include"]) & have:
            return False
    if "development_type" in check and item.development_type != check["development_type"]:
        return False
    if "development_type_one_of" in check and item.development_type not in check["development_type_one_of"]:
        return False
    if "claim_status_one_of" in check and item.claim_status not in check["claim_status_one_of"]:
        return False
    if check.get("reason_required") and not item.reason:
        return False
    return True


def check_merged(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    candidates = [i for i in matches if _item_matches(i, check)]
    if not candidates:
        return False, f"no item from these inputs matched {check}"
    item = candidates[0]
    min_sources = check.get("min_sources", len(case["inputs"]))
    if len(item.sources) < min_sources:
        return False, f"item '{item.title}' cites {len(item.sources)} source(s), need >= {min_sources}"
    return True, f"merged into '{item.title}' with {len(item.sources)} source(s)"

def check_min_item_count(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    ok = len(matches) >= check["count"]
    return ok, f"{len(matches)} item(s) from these inputs (need >= {check['count']})"


def check_max_item_count(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    ok = len(matches) <= check["count"]
    return ok, f"{len(matches)} item(s) from these inputs (need <= {check['count']})"


def check_some_item_matches(case: dict, check: dict, result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    hit = any(_item_matches(i, check) for i in matches)
    return hit, "matching item found" if hit else f"no item matched {check}"


def check_some_item_title_contains(case: dict, check: dict,
                                    result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    hit = any(check["text"].lower() in i.title.lower() for i in matches)
    return hit, f"title containing {check['text']!r} " + ("found" if hit else "not found")


def check_no_item_title_contains(case: dict, check: dict,
                                  result: tg.TriageResult) -> tuple[bool, str]:
    matches = items_from_inputs(result, case["inputs"])
    hit = any(check["text"].lower() in i.title.lower() for i in matches)
    return not hit, (f"unexpectedly found title containing {check['text']!r}" if hit
                      else f"no title contains {check['text']!r}, as expected")


CHECKS = {
    "all_dropped": check_all_dropped,
    "none_become_items": check_none_become_items,
    "no_item_development_type": check_no_item_development_type,
    "merged": check_merged,
    "min_item_count": check_min_item_count,
    "max_item_count": check_max_item_count,
    "some_item_matches": check_some_item_matches,
    "some_item_title_contains": check_some_item_title_contains,
    "no_item_title_contains": check_no_item_title_contains,
}


def score_case(case: dict, result: tg.TriageResult) -> list[tuple[str, bool, str]]:
    out = []
    for check in case["checks"]:
        fn = CHECKS[check["type"]]
        ok, detail = fn(case, check, result)
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
    parser.add_argument("--model", default=tg.DEFAULT_MODEL)
    parser.add_argument("--case", action="append", dest="cases",
                        help="run only this case (repeatable); default: all cases")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        print("no matching cases found", file=sys.stderr)
        return 1

    inputs = union_inputs(cases)
    print(f"running triage over {len(inputs)} capture(s) from {len(cases)} case(s), "
          f"model={args.model}\n")

    result, usage = run_triage_over(inputs, args.model)

    total_checks = 0
    total_passed = 0
    for case in cases:
        print(f"## {case['name']}")
        for check_type, ok, detail in score_case(case, result):
            total_checks += 1
            total_passed += ok
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {check_type}: {detail}")
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
