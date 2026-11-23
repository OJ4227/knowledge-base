#!/usr/bin/env python3
"""Scored eval for the Enrich prompt (tools/prompts/enrich.md + tools/enrich.py).

THIS SCRIPT COSTS REAL MONEY ON EVERY RUN — it calls the Anthropic API once per
invocation. Never invoked by pytest or the pre-commit hook.

Runs Enrich once over the union of every golden case's items (selected from a real Triage
output file by item id), scores each case's deterministic structural checks against the
model's *accepted* actions (after the same hard-guard validation an Enrich preview runs —
rejected actions never count toward a case), and prints a per-case pass/fail table
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
import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import enrich as en
import enrich_resolve as er
import lint

CASES_DIR = Path(__file__).resolve().parent / "cases" / "enrich"
DEFAULT_INPUT = en.ROOT / "inbox" / "_triage" / "2026-10-27.json"
EVAL_MAX_TOKENS = 20_000  # enough for successful full runs; bounds pathological output loops

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


class EvaluationTimeout(TimeoutError):
    pass


@contextmanager
def wall_clock_timeout(seconds: int):
    """Bound a paid eval even if a gateway keeps a streaming response alive forever."""
    if seconds <= 0:
        yield
        return

    def raise_timeout(_signum, _frame):
        raise EvaluationTimeout(f"evaluation exceeded {seconds}s wall-clock limit")

    previous = signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def consume_with_progress(stream, report_every_seconds: float = 15.0):
    """Consume without logging content; report whether a slow call is still emitting."""
    started = time.perf_counter()
    last_report = started
    event_count = 0
    generated_characters = 0
    for event in stream:
        event_count += 1
        delta = getattr(event, "delta", None)
        for field in ("text", "thinking", "partial_json"):
            value = getattr(delta, field, "") if delta is not None else ""
            if isinstance(value, str):
                generated_characters += len(value)
        now = time.perf_counter()
        if now - last_report >= report_every_seconds:
            print(f"stream progress: elapsed={now - started:.1f}s events={event_count} "
                  f"generated_chars={generated_characters}", flush=True)
            last_report = now
    return stream.get_final_message()


def run_enrich_over(item_ids: list[str], input_path: Path, model: str,
                     effort: str = en.tg.DEFAULT_EFFORT,
                     max_tokens: int = EVAL_MAX_TOKENS,
                     wall_timeout_seconds: int = 300,
                     batch_size: int = 0,
                     max_entities: int = en.DEFAULT_MAX_ENTITIES_PER_BATCH):
    all_items = en.load_triage_items(input_path)
    by_id = {i.id: i for i in all_items}
    missing = [i for i in item_ids if i not in by_id]
    if missing:
        print(f"item id(s) not found in {input_path}: {missing}", file=sys.stderr)
        raise SystemExit(1)
    items = [by_id[i] for i in item_ids]

    index = er.build_vault_index(en.ROOT)
    pending = er.load_pending_store()
    batches = (en.make_batches(items, batch_size, index, max_entities)
               if batch_size else [items])

    client = en.tg.build_client()
    if client is None:
        print("No credentials found. Set ANTHROPIC_API_KEY, or ANTHROPIC_BASE_URL + "
              "ANTHROPIC_AUTH_TOKEN for a gateway. Source tools/.env first.",
              file=sys.stderr)
        raise SystemExit(1)

    started = time.perf_counter()
    rejected_pairs = en.load_rejected_pairs()
    accepted: list[en.EnrichAction] = []
    rejected: list[en.Rejection] = []
    usage_totals = SimpleNamespace(
        input_tokens=0, output_tokens=0,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    for number, batch in enumerate(batches, 1):
        print(f"eval batch {number}/{len(batches)}: {len(batch)} item(s)", flush=True)
        static_prompt, items_prompt = en.build_prompt_parts(batch, index, pending)
        with wall_clock_timeout(wall_timeout_seconds):
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                timeout=120.0,
                thinking={"type": "adaptive"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": static_prompt,
                         "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": items_prompt},
                    ],
                }],
                output_config={
                    "effort": effort,
                    "format": {
                        "type": "json_schema",
                        "schema": en.EnrichResult.model_json_schema(),
                    },
                },
            ) as stream:
                response = consume_with_progress(stream)

        for field in vars(usage_totals):
            setattr(usage_totals, field, getattr(usage_totals, field)
                    + getattr(response.usage, field, 0))

        text = next(block.text for block in response.content if block.type == "text")
        print(f"batch response: stop_reason={response.stop_reason} "
              f"output_tokens={response.usage.output_tokens} chars={len(text)}",
              flush=True)
        actions = en.normalize_actions(en.EnrichResult.model_validate_json(text))
        batch_accepted, batch_rejected = en.validate_actions(
            actions, index, rejected_pairs,
            {item.id for item in batch if item.development_type == "opinion"},
            resolution_map=en.build_resolution_map(batch, index, pending),
            expected_item_ids={item.id for item in batch},
        )
        accepted.extend(batch_accepted)
        rejected.extend(batch_rejected)
        en.advance_planning_state(batch_accepted, index, pending)

    return accepted, rejected, usage_totals, time.perf_counter() - started


# --------------------------------------------------------------------------- scoring

def _note_stem(path: str | None) -> str | None:
    return Path(path).stem if path else None


def _action_matches(a: en.EnrichAction, check: dict) -> bool:
    if "action_type" in check and a.action_type != check["action_type"]:
        return False
    if "target_note" in check and a.target_note != check["target_note"]:
        return False
    # target_note is one unified field now (existing note, new note's intended path, or
    # thread, depending on action_type) — target_note_stem and the legacy new_note_path_stem
    # name both just read it.
    if "target_note_stem" in check and _note_stem(a.target_note) != check["target_note_stem"]:
        return False
    if "new_note_type" in check and a.new_note.type != check["new_note_type"]:
        return False
    if "new_note_path_stem" in check and _note_stem(a.target_note) != check["new_note_path_stem"]:
        return False
    if "frontmatter_field" in check and a.frontmatter_patch.field != check["frontmatter_field"]:
        return False
    if "entity" in check and a.entity != check["entity"]:
        return False
    if "sources_include" in check:
        sources = a.timeline_entry.sources
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
    parser.add_argument("--max-tokens", type=int, default=EVAL_MAX_TOKENS,
                        help=f"maximum output tokens (default: {EVAL_MAX_TOKENS})")
    parser.add_argument("--wall-timeout", type=int, default=300,
                        help="hard wall-clock limit in seconds (default: 300; 0 disables)")
    parser.add_argument("--batch-size", type=int, default=0,
                        help="maximum items per call; 0 keeps the eval in one call")
    parser.add_argument("--max-entities", type=int, default=en.DEFAULT_MAX_ENTITIES_PER_BATCH,
                        help="maximum entity mentions per batched call")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        print("no matching cases found", file=sys.stderr)
        return 1

    item_ids = union_item_ids(cases)
    print(f"running enrich over {len(item_ids)} item(s) from {len(cases)} case(s), "
          f"model={args.model}, effort={args.effort}, input={args.input}\n")

    try:
        accepted, rejected, usage, elapsed_seconds = run_enrich_over(
            item_ids, args.input, args.model, args.effort,
            max_tokens=args.max_tokens,
            wall_timeout_seconds=args.wall_timeout,
            batch_size=args.batch_size,
            max_entities=args.max_entities,
        )
    except EvaluationTimeout as exc:
        print(f"EVAL TIMEOUT: {exc}", file=sys.stderr)
        return 2

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
    print(f"latency: {elapsed_seconds:.1f}s")
    print(f"actions: accepted={len(accepted)} rejected={len(rejected)}")
    cost = estimate_cost(args.model, usage)
    if cost is not None:
        print(f"estimated cost: ${cost:.4f}")

    return 0 if total_passed == total_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
