#!/usr/bin/env python3
"""Stage 3 pipeline step: Enrich.

Reads a Triage output file (`inbox/_triage/YYYY-MM-DD.json`), resolves each item's
entities against the vault (`tools/enrich_resolve.py`), and asks the model to propose
structured actions: timeline entries on existing notes, frontmatter rollups, new notes for
entities that clear the "≥2 mentions" bar, concept links, opinion-to-thread links, and
explicit skips. A Python layer enforces the rules that must never be violated (every
timeline entry cited, no opinion item gets a timeline entry, no name collision, nothing in
`meta/rejected-links.md`) and performs the actual file edits — the model never writes a
full file verbatim. See `DESIGN.md` §7 and `meta/agent-instructions/enrich.md` for how this
fits the pipeline.

Usage:
    python tools/enrich.py --input inbox/_triage/2026-10-27.json
    python tools/enrich.py --apply-plan meta/review/enrich-plans/<plan>.json
    python tools/enrich.py --input inbox/_triage/2026-10-27.json --dry-run

Requires one of, in the environment (source tools/.env first):
  - ANTHROPIC_API_KEY                         — direct Anthropic API
  - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN — a gateway/proxy in front of the API
    (e.g. a corporate relay) that speaks Bearer auth instead of an Anthropic key
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

import enrich_resolve as er
import lint
import triage as tg  # reuse build_client(), DEFAULT_MODEL, DEFAULT_EFFORT

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "tools" / "prompts" / "enrich.md"
ENRICH_RULES_PATH = ROOT / "meta" / "agent-instructions" / "enrich.md"
HARD_RULES_PATH = ROOT / "meta" / "agent-instructions" / "hard-rules.md"
SCHEMA_PATH = ROOT / "meta" / "schema.md"
TAXONOMY_PATH = ROOT / "meta" / "taxonomy.md"
REJECTED_LINKS_PATH = ROOT / "meta" / "rejected-links.md"
TEMPLATES_DIR = ROOT / "templates"
PLAN_DIR = ROOT / "meta" / "review" / "enrich-plans"
PLAN_FORMAT_VERSION = 1

ACTION_TYPES = ("timeline_entry", "frontmatter_patch", "new_note", "concept_link",
                "key_link", "pending_fact", "skip")
NOTE_TYPES = ("company", "person", "technology", "moc")
VOLATILE_FIELDS = ("total_funding_usd", "last_round", "stage", "status")
TYPE_DIR = {"company": "companies", "person": "people", "technology": "technologies",
            "moc": "topics"}
TEMPLATE_FILE = {"company": "company.md", "person": "person.md",
                 "technology": "technology.md", "moc": "topic.md"}
DEFAULT_BATCH_SIZE = 12
DEFAULT_MAX_ENTITIES_PER_BATCH = 40
MAX_TOKENS_PER_BATCH = 20_000


# --------------------------------------------------------------------------- schema
#
# The model-facing schema uses one required list per action type. This avoids both the
# nullable-field `anyOf` explosion that Vertex rejected and the sentinel defaults that let
# a `pending_fact` omit its payload while remaining schema-valid. `EnrichAction` below is
# only an internal normalized representation; it is not included in the JSON schema sent
# to the model.

class TimelineEntrySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    text: str = Field(min_length=1)
    tag: Literal["milestone", "routine"]
    claim_tag: Literal["claim/reported", "claim/rumored", "claim/disputed", ""]
    sources: list[str] = Field(min_length=1)


class FrontmatterPatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal[VOLATILE_FIELDS]
    value: str = Field(min_length=1)


class NewNoteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[NOTE_TYPES]
    frontmatter_yaml: str = Field(min_length=1)
    timeline_entries: list[TimelineEntrySpec] = Field(min_length=1)


class KeyLinkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    source: str = Field(min_length=1)


class TimelineEntryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    target_note: str
    timeline_entry: TimelineEntrySpec


class FrontmatterPatchAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    target_note: str
    frontmatter_patch: FrontmatterPatchSpec


class NewNoteAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    entity: str
    target_note: str
    new_note: NewNoteSpec


class ConceptLinkAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    target_note: str
    concept: str


class KeyLinkAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    target_note: str
    key_link: KeyLinkSpec


class PendingFactAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    entity: str
    timeline_entry: TimelineEntrySpec


class SkipAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    reason: str


class EnrichAction(BaseModel):
    """Normalized internal action. Not part of the model-facing output schema."""
    model_config = ConfigDict(extra="forbid")

    action_type: Literal[ACTION_TYPES]
    item_id: str
    target_note: str = ""
    timeline_entry: TimelineEntrySpec | None = None
    frontmatter_patch: FrontmatterPatchSpec | None = None
    new_note: NewNoteSpec | None = None
    concept: str = ""
    key_link: KeyLinkSpec | None = None
    entity: str = ""
    reason: str = ""


class EnrichResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeline_entries: list[TimelineEntryAction]
    frontmatter_patches: list[FrontmatterPatchAction]
    new_notes: list[NewNoteAction]
    concept_links: list[ConceptLinkAction]
    key_links: list[KeyLinkAction]
    pending_facts: list[PendingFactAction]
    skips: list[SkipAction]


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str


class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["sha256"]
    digest: str
    files: dict[str, str]


class PlanRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: EnrichAction
    reason: str


class PlanAmendment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["reroute_new_note"]
    entity: str
    target_note: str
    kept_timeline_indexes: list[int]
    removed_pending_fact_count: int = 0
    reason: str
    amended_at: str


class EnrichPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: Literal[PLAN_FORMAT_VERSION]
    created_at: str
    input: PlanInput
    model: str
    effort: str
    output_schema_sha256: str
    actions_sha256: str
    rejections_sha256: str
    state: StateFingerprint
    actions: list[EnrichAction]
    rejections: list[PlanRejection]
    amendments: list[PlanAmendment] = Field(default_factory=list)


def normalize_actions(result: EnrichResult) -> list[EnrichAction]:
    """Flatten typed model output into the stable internal action pipeline."""
    actions: list[EnrichAction] = []
    actions.extend(EnrichAction(action_type="timeline_entry", **a.model_dump())
                   for a in result.timeline_entries)
    actions.extend(EnrichAction(action_type="frontmatter_patch", **a.model_dump())
                   for a in result.frontmatter_patches)
    actions.extend(EnrichAction(action_type="new_note", **a.model_dump())
                   for a in result.new_notes)
    actions.extend(EnrichAction(action_type="concept_link", **a.model_dump())
                   for a in result.concept_links)
    actions.extend(EnrichAction(action_type="key_link", **a.model_dump())
                   for a in result.key_links)
    actions.extend(EnrichAction(action_type="pending_fact", **a.model_dump())
                   for a in result.pending_facts)
    actions.extend(EnrichAction(action_type="skip", **a.model_dump())
                   for a in result.skips)
    return actions


# --------------------------------------------------------------------------- loading triage output

@dataclass
class TriageItemView:
    id: str
    title: str
    summary: str
    domains: list[str]
    development_type: str
    entities: list[str]
    concepts: list[str]
    sources: list[str]
    claim_status: str
    reason: str | None


def load_triage_items(path: Path) -> list[TriageItemView]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [TriageItemView(**item) for item in data["items"]]


# --------------------------------------------------------------------------- plan artifacts

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def output_schema_sha256() -> str:
    schema = json.dumps(EnrichResult.model_json_schema(), sort_keys=True,
                        separators=(",", ":")).encode()
    return hashlib.sha256(schema).hexdigest()


def actions_sha256(actions: list[EnrichAction]) -> str:
    data = [action.model_dump(mode="json") for action in actions]
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def rejections_sha256(rejections: list[PlanRejection]) -> str:
    data = [rejection.model_dump(mode="json") for rejection in rejections]
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def state_input_paths() -> list[Path]:
    """Return every repository file that can affect planning or application."""
    paths = set(er.iter_resolution_paths(ROOT))
    paths.update((
        PROMPT_PATH, ENRICH_RULES_PATH, HARD_RULES_PATH, SCHEMA_PATH, TAXONOMY_PATH,
        REJECTED_LINKS_PATH, er.PENDING_ENTITIES_PATH,
    ))
    if TEMPLATES_DIR.exists():
        paths.update(TEMPLATES_DIR.glob("*.md"))
    return sorted(paths, key=lambda path: relative_path(path))


def build_state_fingerprint() -> StateFingerprint:
    files = {
        relative_path(path): sha256_file(path) if path.exists() else "<missing>"
        for path in state_input_paths()
    }
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return StateFingerprint(
        algorithm="sha256",
        digest=hashlib.sha256(encoded).hexdigest(),
        files=files,
    )


def changed_state_files(expected: StateFingerprint,
                        actual: StateFingerprint) -> list[str]:
    paths = set(expected.files) | set(actual.files)
    return sorted(path for path in paths
                  if expected.files.get(path) != actual.files.get(path))


def default_plan_path(input_path: Path) -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PLAN_DIR / f"{input_path.stem}--{timestamp}.json"


def build_plan(input_path: Path, model: str, effort: str,
               actions: list[EnrichAction],
               rejections: list[Rejection] | None = None) -> EnrichPlan:
    plan_rejections = [
        PlanRejection(action=rejection.action, reason=rejection.reason)
        for rejection in (rejections or [])
    ]
    return EnrichPlan(
        format_version=PLAN_FORMAT_VERSION,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        input=PlanInput(path=relative_path(input_path), sha256=sha256_file(input_path)),
        model=model,
        effort=effort,
        output_schema_sha256=output_schema_sha256(),
        actions_sha256=actions_sha256(actions),
        rejections_sha256=rejections_sha256(plan_rejections),
        state=build_state_fingerprint(),
        actions=actions,
        rejections=plan_rejections,
        amendments=[],
    )


def write_plan(plan: EnrichPlan, path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing plan: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_plan(path: Path) -> EnrichPlan:
    return EnrichPlan.model_validate_json(path.read_text(encoding="utf-8"))


def verify_plan_is_current(plan: EnrichPlan) -> list[str]:
    problems: list[str] = []
    input_path = ROOT / plan.input.path
    if not input_path.exists():
        problems.append(f"input file is missing: {plan.input.path}")
    elif sha256_file(input_path) != plan.input.sha256:
        problems.append(f"input file changed: {plan.input.path}")

    current_schema_hash = output_schema_sha256()
    if current_schema_hash != plan.output_schema_sha256:
        problems.append("Enrich output schema changed")
    if actions_sha256(plan.actions) != plan.actions_sha256:
        problems.append("plan actions changed after preview")
    if rejections_sha256(plan.rejections) != plan.rejections_sha256:
        problems.append("plan rejection audit changed after preview")

    current_state = build_state_fingerprint()
    if current_state.digest != plan.state.digest:
        changed = changed_state_files(plan.state, current_state)
        problems.append("vault state changed: " + ", ".join(changed))
    return problems


def reroute_new_note(plan: EnrichPlan, entity: str, target_note: str,
                     kept_timeline_indexes: list[int], reason: str) -> None:
    """Replace one proposed note with selected timeline entries on its owning company."""
    matches = [
        (index, action)
        for index, action in enumerate(plan.actions)
        if action.action_type == "new_note"
        and lint.resolve_key(action.entity) == lint.resolve_key(entity)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one new_note for {entity!r}, found {len(matches)}")
    action_index, action = matches[0]
    assert action.new_note is not None

    existing_targets = {
        note.rel for note in er.build_vault_index(ROOT).by_name.values()
    }
    planned_targets = {
        candidate.target_note
        for candidate in plan.actions[:action_index]
        if candidate.action_type == "new_note"
    }
    if target_note not in existing_targets | planned_targets:
        raise ValueError(
            f"reroute target {target_note!r} must exist before the source new_note"
        )

    entries = action.new_note.timeline_entries
    if any(index < 0 or index >= len(entries) for index in kept_timeline_indexes):
        raise ValueError(f"timeline index out of range for {entity!r}")

    replacements = [
        EnrichAction(
            action_type="timeline_entry",
            item_id=action.item_id,
            target_note=target_note,
            timeline_entry=entries[index],
        )
        for index in kept_timeline_indexes
    ]
    pending_facts_to_remove = {
        index
        for index, candidate in enumerate(plan.actions)
        if candidate.action_type == "pending_fact"
        and lint.resolve_key(candidate.entity) == lint.resolve_key(entity)
    }
    amended_actions: list[EnrichAction] = []
    for index, candidate in enumerate(plan.actions):
        if index in pending_facts_to_remove:
            continue
        if index == action_index:
            amended_actions.extend(replacements)
            continue
        amended_actions.append(candidate)
    plan.actions = amended_actions
    plan.amendments.append(PlanAmendment(
        kind="reroute_new_note",
        entity=entity,
        target_note=target_note,
        kept_timeline_indexes=kept_timeline_indexes,
        removed_pending_fact_count=len(pending_facts_to_remove),
        reason=reason,
        amended_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    ))
    plan.actions_sha256 = actions_sha256(plan.actions)


def amend_saved_plan(source_path: Path, output_path: Path,
                     reroutes: list[tuple[str, str, list[int], str]]) -> EnrichPlan:
    """Create a new checksummed plan containing explicit owner-reviewed reroutes."""
    plan = load_plan(source_path)
    input_path = ROOT / plan.input.path
    if not input_path.exists() or sha256_file(input_path) != plan.input.sha256:
        raise ValueError("Triage input changed; refusing to amend the plan")
    if output_schema_sha256() != plan.output_schema_sha256:
        raise ValueError("Enrich output schema changed; refusing to amend the plan")
    if actions_sha256(plan.actions) != plan.actions_sha256:
        raise ValueError("source plan actions changed after preview")
    if rejections_sha256(plan.rejections) != plan.rejections_sha256:
        raise ValueError("source plan rejection audit changed after preview")

    current_state = build_state_fingerprint()
    changed = changed_state_files(plan.state, current_state)
    allowed_policy_changes = {
        relative_path(PROMPT_PATH),
        relative_path(ENRICH_RULES_PATH),
        relative_path(HARD_RULES_PATH),
    }
    unexpected = sorted(set(changed) - allowed_policy_changes)
    if unexpected:
        raise ValueError(
            "non-policy planning inputs changed: " + ", ".join(unexpected)
        )

    for entity, target_note, kept_indexes, reason in reroutes:
        reroute_new_note(plan, entity, target_note, kept_indexes, reason)
    plan.state = current_state
    write_plan(plan, output_path)
    return plan


# --------------------------------------------------------------------------- rejected links

def load_rejected_pairs(path: Path = REJECTED_LINKS_PATH) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    pairs = set()
    for m in re.finditer(r"\[\[([^\]]+)\]\]\s*↔\s*\[\[([^\]]+)\]\]", text):
        a, b = lint.resolve_key(m.group(1)), lint.resolve_key(m.group(2))
        pairs.add((a, b))
        pairs.add((b, a))
    return pairs


# --------------------------------------------------------------------------- prompt assembly

def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL).strip()


def load_enrich_rules() -> str:
    return strip_frontmatter(ENRICH_RULES_PATH.read_text(encoding="utf-8"))


def load_hard_rules() -> str:
    return strip_frontmatter(HARD_RULES_PATH.read_text(encoding="utf-8"))


def load_schema_excerpts() -> str:
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    start = text.index("## `company`")
    end = text.index("## `source`")
    company_through_moc = text[start:end].strip()
    timeline_start = text.index("## Timeline entry format")
    timeline_format = text[timeline_start:].strip()
    return company_through_moc + "\n\n" + timeline_format


def load_sector_vocabulary() -> str:
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    start = text.index("## Company sectors")
    end = text.index("## Starter threads")
    return text[start:end].strip()


def render_resolution(name: str, resolution: er.Resolution) -> str:
    if resolution.kind == "matched":
        return f"  - {name!r} -> matched: {resolution.note.rel}"
    if resolution.kind == "pending_second_mention":
        facts = "; ".join(f.text for f in resolution.prior_facts) or "(via existing unresolved link)"
        return f"  - {name!r} -> pending (second mention, eligible for a new note now): {facts}"
    return f"  - {name!r} -> pending (first mention, not yet eligible)"


def render_items_block(items: list[TriageItemView], index: er.VaultIndex,
                        pending: er.PendingStore) -> str:
    parts = []
    for item in items:
        resolutions = "\n".join(
            render_resolution(e, er.resolve_entity(e, index, pending)) for e in item.entities
        )
        parts.append(
            f"### {item.id}\n"
            f"- title: {item.title}\n"
            f"- summary: {item.summary}\n"
            f"- domains: {item.domains}\n"
            f"- development_type: {item.development_type}\n"
            f"- concepts: {item.concepts}\n"
            f"- sources: {item.sources}\n"
            f"- claim_status: {item.claim_status}\n"
            f"- reason: {item.reason}\n"
            f"- entity resolutions:\n{resolutions}\n"
        )
    return "\n".join(parts)


def build_resolution_map(items: list[TriageItemView], index: er.VaultIndex,
                         pending: er.PendingStore) -> dict[str, dict[str, er.Resolution]]:
    return {
        item.id: {
            lint.resolve_key(entity): er.resolve_entity(entity, index, pending)
            for entity in item.entities
        }
        for item in items
    }


def build_prompt_parts(items: list[TriageItemView], index: er.VaultIndex,
                       pending: er.PendingStore) -> tuple[str, str]:
    """Return a cacheable static prefix and the changing item block separately."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    static_prompt = template.format(
        enrich_rules=load_enrich_rules(),
        hard_rules=load_hard_rules(),
        schema_excerpts=load_schema_excerpts(),
        sector_vocabulary=load_sector_vocabulary(),
        items="",
    )
    return static_prompt.rstrip(), render_items_block(items, index, pending)


def build_prompt(items: list[TriageItemView], index: er.VaultIndex,
                  pending: er.PendingStore) -> str:
    static_prompt, items_prompt = build_prompt_parts(items, index, pending)
    return f"{static_prompt}\n\n{items_prompt}"


# --------------------------------------------------------------------------- hard guards

@dataclass
class Rejection:
    action: EnrichAction
    reason: str


def format_timeline_line(t: TimelineEntrySpec) -> str:
    tags = f"#{t.tag}"
    if t.claim_tag:  # "" (unset sentinel) is falsy, same as the old None check
        tags += f" #{t.claim_tag}"
    sources = " ".join(t.sources)
    return f"- {t.date} — {t.text} ({sources}) {tags}"


def validate_new_note_spec(action: EnrichAction) -> str | None:
    assert action.new_note is not None
    try:
        frontmatter = yaml.safe_load(action.new_note.frontmatter_yaml)
    except yaml.YAMLError as exc:
        return f"new_note frontmatter is invalid YAML: {exc}"
    if not isinstance(frontmatter, dict):
        return "new_note frontmatter must be a YAML mapping"
    if frontmatter.get("type") != action.new_note.type:
        return (f"new_note type mismatch: action says {action.new_note.type!r}, "
                f"frontmatter says {frontmatter.get('type')!r}")
    if lint.resolve_key(str(frontmatter.get("name", ""))) != lint.resolve_key(action.entity):
        return "new_note frontmatter name must match the resolved entity"

    target = Path(action.target_note)
    if target.is_absolute() or ".." in target.parts or target.suffix != ".md":
        return "new_note target must be a relative markdown path inside the vault"
    if not target.parts or target.parts[0] != TYPE_DIR[action.new_note.type]:
        return (f"new_note target directory must be "
                f"{TYPE_DIR[action.new_note.type]!r} for type {action.new_note.type!r}")

    note = lint.Note(
        path=ROOT / target,
        rel=target.as_posix(),
        fm=frontmatter,
        body="",
    )
    findings = (
        lint.check_frontmatter(note)
        + lint.check_schema(note)
        + lint.check_field_types(note)
        + lint.check_sectors(note)
    )
    if findings:
        details = "; ".join(f"{finding.rule}: {finding.message}" for finding in findings)
        return f"new_note frontmatter failed schema checks: {details}"
    return None


def validate_actions(actions: list[EnrichAction], index: er.VaultIndex,
                      rejected_pairs: set[tuple[str, str]],
                      opinion_item_ids: set[str],
                      resolution_map: dict[str, dict[str, er.Resolution]] | None = None,
                      expected_item_ids: set[str] | None = None,
                      ) -> tuple[list[EnrichAction], list[Rejection]]:
    """Defense in depth: enforce the rules that must never be violated, regardless of what
    the model proposed. Returns (accepted, rejected)."""
    accepted: list[EnrichAction] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()
    accepted_timeline_keys: set[tuple[str, str]] = set()

    for a in actions:
        fingerprint = a.model_dump_json()
        if fingerprint in seen:
            rejected.append(Rejection(a, "duplicate action"))
            continue
        seen.add(fingerprint)

        if a.action_type == "skip":
            accepted.append(a)
            continue

        if a.action_type == "timeline_entry":
            if a.item_id in opinion_item_ids:
                rejected.append(Rejection(a, "opinion items never get a timeline_entry "
                                             "(DESIGN.md §2 — opinion is a ledger exception)"))
                continue
            if not a.target_note or lint.resolve_key(a.target_note) not in index.by_name:
                rejected.append(Rejection(a, f"target_note {a.target_note!r} not found in vault index"))
                continue
            if a.timeline_entry is None or not a.timeline_entry.sources:
                rejected.append(Rejection(a, "timeline_entry with zero sources (hard rule 2)"))
                continue
            accepted.append(a)
            accepted_timeline_keys.add((a.item_id, lint.resolve_key(a.target_note)))
            continue

        if a.action_type == "frontmatter_patch":
            if not a.target_note or lint.resolve_key(a.target_note) not in index.by_name:
                rejected.append(Rejection(a, f"target_note {a.target_note!r} not found in vault index"))
                continue
            if a.frontmatter_patch is None:
                rejected.append(Rejection(a, "frontmatter_patch missing field/value"))
                continue
            support_key = (a.item_id, lint.resolve_key(a.target_note))
            if support_key not in accepted_timeline_keys:
                rejected.append(Rejection(a, "frontmatter_patch has no accepted timeline_entry "
                                             "for the same item and target note"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "new_note":
            if not a.target_note or a.new_note is None:
                rejected.append(Rejection(a, "new_note missing path/type"))
                continue
            stem = Path(a.target_note).stem
            if lint.resolve_key(stem) in index.by_name:
                rejected.append(Rejection(a, f"name/alias collision: {stem!r} already resolves "
                                             f"to {index.by_name[lint.resolve_key(stem)].rel}"))
                continue
            spec_error = validate_new_note_spec(a)
            if spec_error:
                rejected.append(Rejection(a, spec_error))
                continue
            resolution = None
            if resolution_map is not None:
                resolution = resolution_map.get(a.item_id, {}).get(lint.resolve_key(a.entity))
                if resolution is None or resolution.kind != "pending_second_mention":
                    kind = resolution.kind if resolution else "not present in item"
                    rejected.append(Rejection(a, f"new_note entity must resolve as pending second "
                                                 f"mention, got {kind}"))
                    continue
            if a.item_id in opinion_item_ids:
                prior_lines = {
                    fact.text for fact in (resolution.prior_facts if resolution else [])
                }
                emitted_lines = {
                    format_timeline_line(entry) for entry in a.new_note.timeline_entries
                }
                if not prior_lines or not emitted_lines.issubset(prior_lines):
                    rejected.append(Rejection(
                        a, "opinion-triggered new_note may contain only verbatim timeline "
                           "facts stored before the opinion item (DESIGN.md §2)",
                    ))
                    continue
            accepted.append(a)
            continue

        if a.action_type == "concept_link":
            if lint.resolve_key(a.concept) not in index.by_name:
                rejected.append(Rejection(a, f"concept {a.concept!r} has no existing concept "
                                             f"note — never auto-create one (hard rule 6)"))
                continue
            pair = (lint.resolve_key(a.target_note), lint.resolve_key(a.concept))
            if pair in rejected_pairs:
                rejected.append(Rejection(a, "link rejected previously — see meta/rejected-links.md"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "key_link":
            if not a.target_note or lint.resolve_key(a.target_note) not in index.by_name:
                rejected.append(Rejection(a, f"target_note {a.target_note!r} not found in vault index"))
                continue
            if a.key_link is None:
                rejected.append(Rejection(a, "key_link missing payload"))
                continue
            accepted.append(a)
            continue

        if a.action_type == "pending_fact":
            if a.item_id in opinion_item_ids:
                rejected.append(Rejection(a, "opinion items never produce a storable fact, "
                                             "pending or otherwise (DESIGN.md §2)"))
                continue
            if not a.entity:
                rejected.append(Rejection(a, "pending_fact missing entity name"))
                continue
            if lint.resolve_key(a.entity) in index.by_name:
                rejected.append(Rejection(a, f"entity {a.entity!r} already resolves to "
                                             f"{index.by_name[lint.resolve_key(a.entity)].rel} — "
                                             f"use timeline_entry on that note instead"))
                continue
            if a.timeline_entry is None or not a.timeline_entry.sources:
                rejected.append(Rejection(a, "pending_fact with zero sources (hard rule 2)"))
                continue
            if resolution_map is not None:
                resolution = resolution_map.get(a.item_id, {}).get(lint.resolve_key(a.entity))
                if resolution is None or resolution.kind != "pending_first_mention":
                    kind = resolution.kind if resolution else "not present in item"
                    rejected.append(Rejection(a, f"pending_fact entity must resolve as pending first "
                                                 f"mention, got {kind}"))
                    continue
            accepted.append(a)
            continue

    if expected_item_ids is not None:
        covered = {a.item_id for a in actions}
        for item_id in sorted(expected_item_ids - covered):
            missing = EnrichAction(action_type="skip", item_id=item_id,
                                   reason="model returned no action for this item")
            rejected.append(Rejection(missing, "item has no action in any output bucket"))

    return accepted, rejected


# --------------------------------------------------------------------------- applying actions

def insert_line_in_year_section(section: str, heading: str, line: str, date: str) -> str:
    heading_end = section.index(heading) + len(heading)
    remaining = section[heading_end:]
    next_heading = re.search(r"\n### ", remaining[1:])
    year_end = heading_end + (1 + next_heading.start() if next_heading else len(remaining))
    year_content = section[heading_end:year_end]

    entries = list(re.finditer(r"(?m)^- (\d{4}-\d{2}-\d{2}) —", year_content))
    insert_at = 1 if year_content.startswith("\n") else 0
    for entry in entries:
        if date >= entry.group(1):
            insert_at = entry.start()
            break
    else:
        if entries:
            line_end = year_content.find("\n", entries[-1].start())
            insert_at = len(year_content) if line_end == -1 else line_end + 1

    updated_content = year_content[:insert_at] + line + "\n" + year_content[insert_at:]
    return section[:heading_end] + updated_content + section[year_end:]


def insert_timeline_bullet(body: str, line: str, date: str) -> str:
    """Insert `line` under the `### YYYY` heading matching `date`'s year, newest-first.
    Creates the year heading (in the right position) if it doesn't exist yet."""
    year = date[:4]
    heading = f"### {year}"
    timeline_idx = body.index("## Timeline")
    section_end = len(body)
    next_heading = re.search(r"\n## ", body[timeline_idx + 1:])
    if next_heading:
        section_end = timeline_idx + 1 + next_heading.start()
    section = body[timeline_idx:section_end]

    if heading in section:
        new_section = insert_line_in_year_section(section, heading, line, date)
    else:
        # insert the new year heading in descending order among existing ### headings
        year_headings = [(m.group(1), m.start()) for m in re.finditer(r"### (\d{4})", section)]
        insert_pos = len(section)
        for y, pos in year_headings:
            if year > y:
                insert_pos = pos
                break
        new_section = section[:insert_pos] + f"{heading}\n{line}\n\n" + section[insert_pos:]

    return body[:timeline_idx] + new_section + body[section_end:]


def apply_frontmatter_patch(path: Path, field_name: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm_text) or {}
    parsed_value = yaml.safe_load(value)
    data[field_name] = parsed_value
    data["updated"] = dt.date.today().isoformat()
    new_fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")


def apply_timeline_entry(path: Path, entry: TimelineEntrySpec) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    data = yaml.safe_load(fm_text) or {}
    data["updated"] = dt.date.today().isoformat()
    new_fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()

    line = format_timeline_line(entry)
    new_body = insert_timeline_bullet(body, line, entry.date)
    path.write_text(f"---\n{new_fm}\n---\n{new_body}", encoding="utf-8")


def apply_concept_link(path: Path, concept_target: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    link = f"[[{concept_target}]]"
    if link in body:
        return
    dev_idx = body.find("## Developments")
    if dev_idx != -1:
        insert_at = body.index("\n", dev_idx) + 1
        body = body[:insert_at] + f"\n- {link}\n" + body[insert_at:]
    else:
        body = body.rstrip() + f"\n\n## Related concepts\n\n- {link}\n"
    path.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def apply_key_link(path: Path, text_line: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    fm_text, body = lint.split_frontmatter(text)
    kl_idx = body.rfind("## Key links")
    entry = f"- {text_line} ({source})"
    insert_at = body.index("\n", kl_idx) + 1 if kl_idx != -1 else len(body)
    body = body[:insert_at] + f"{entry}\n" + body[insert_at:]
    path.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def apply_pending_fact(store: er.PendingStore, action: EnrichAction) -> None:
    assert action.timeline_entry is not None
    fact = er.PendingFact(text=format_timeline_line(action.timeline_entry))
    store.facts.setdefault(action.entity, []).append(fact)


def finalize_new_note_body(template_body: str, note_name: str) -> str:
    timeline_placeholder = "\n### YYYY\n\n-\n"
    if timeline_placeholder not in template_body:
        raise ValueError("new-note template is missing the timeline placeholder")
    return template_body.replace("<note name>", note_name).replace(
        timeline_placeholder, "\n", 1
    )


def create_new_note(action: EnrichAction) -> Path:
    assert action.new_note is not None
    template_path = TEMPLATES_DIR / TEMPLATE_FILE[action.new_note.type]
    template_text = template_path.read_text(encoding="utf-8")
    _tmpl_fm, tmpl_body = lint.split_frontmatter(template_text)

    patch = yaml.safe_load(action.new_note.frontmatter_yaml or "{}") or {}
    today = dt.date.today().isoformat()
    patch["created"] = today
    patch["updated"] = today

    new_fm = yaml.safe_dump(patch, sort_keys=False, allow_unicode=True).strip()

    note_name = str(patch.get("name") or action.entity)
    body = finalize_new_note_body(tmpl_body, note_name)
    for entry in sorted(action.new_note.timeline_entries, key=lambda candidate: candidate.date):
        line = format_timeline_line(entry)
        body = insert_timeline_bullet(body, line, entry.date)

    out_path = ROOT / action.target_note
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- preview / apply

def describe_action(a: EnrichAction) -> str:
    if a.action_type == "timeline_entry":
        assert a.timeline_entry is not None
        return (f"[timeline_entry] {a.target_note}: "
                f"{format_timeline_line(a.timeline_entry)}")
    if a.action_type == "frontmatter_patch":
        assert a.frontmatter_patch is not None
        return (f"[frontmatter_patch] {a.target_note}: "
                f"{a.frontmatter_patch.field} = {a.frontmatter_patch.value}")
    if a.action_type == "new_note":
        assert a.new_note is not None
        lines = "\n".join(f"    {format_timeline_line(t)}"
                          for t in a.new_note.timeline_entries)
        return f"[new_note] {a.target_note} ({a.new_note.type})\n{lines}"
    if a.action_type == "concept_link":
        return f"[concept_link] {a.target_note}: [[{a.concept}]]"
    if a.action_type == "key_link":
        assert a.key_link is not None
        return f"[key_link] {a.target_note}: {a.key_link.text} ({a.key_link.source})"
    if a.action_type == "pending_fact":
        assert a.timeline_entry is not None
        return f"[pending_fact] {a.entity}: {format_timeline_line(a.timeline_entry)}"
    return f"[skip] {a.item_id}: {a.reason}"


def apply_action(a: EnrichAction, pending: er.PendingStore) -> None:
    if a.action_type == "timeline_entry":
        assert a.timeline_entry is not None
        apply_timeline_entry(ROOT / a.target_note, a.timeline_entry)
    elif a.action_type == "frontmatter_patch":
        assert a.frontmatter_patch is not None
        apply_frontmatter_patch(ROOT / a.target_note, a.frontmatter_patch.field,
                                 a.frontmatter_patch.value)
    elif a.action_type == "new_note":
        create_new_note(a)
        pending.facts.pop(a.entity, None)
    elif a.action_type == "concept_link":
        apply_concept_link(ROOT / a.target_note, a.concept)
    elif a.action_type == "key_link":
        assert a.key_link is not None
        apply_key_link(ROOT / a.target_note, a.key_link.text, a.key_link.source)
    elif a.action_type == "pending_fact":
        apply_pending_fact(pending, a)
    # skip: nothing to apply


def touched_paths(actions: list[EnrichAction]) -> list[Path]:
    paths = [ROOT / a.target_note for a in actions
             if a.action_type not in ("skip", "pending_fact")]
    if any(a.action_type in ("pending_fact", "new_note") for a in actions):
        paths.append(er.PENDING_ENTITIES_PATH)
    return list(dict.fromkeys(paths))  # de-dup, preserve order


def make_batches(items: list[TriageItemView], batch_size: int,
                 index: er.VaultIndex,
                 max_entities: int = DEFAULT_MAX_ENTITIES_PER_BATCH,
                 ) -> list[list[TriageItemView]]:
    """Create bounded batches and separate repeated unresolved entities.

    A repeated unknown entity must be resolved after the earlier batch has either stored a
    fact or skipped it; putting both mentions in one prompt would resolve both against the
    same stale pre-batch state.
    """
    if batch_size < 1 or max_entities < 1:
        raise ValueError("batch_size and max_entities must be at least 1")

    batches: list[list[TriageItemView]] = []
    current: list[TriageItemView] = []
    current_unresolved: set[str] = set()
    current_entity_count = 0
    for item in items:
        unresolved = {
            lint.resolve_key(entity)
            for entity in item.entities
            if lint.resolve_key(entity) not in index.by_name
        }
        exceeds_entity_budget = current_entity_count + len(item.entities) > max_entities
        if current and (len(current) >= batch_size or exceeds_entity_budget
                        or current_unresolved & unresolved):
            batches.append(current)
            current = []
            current_unresolved = set()
            current_entity_count = 0
        current.append(item)
        current_unresolved.update(unresolved)
        current_entity_count += len(item.entities)
    if current:
        batches.append(current)
    return batches


def add_virtual_note(index: er.VaultIndex, action: EnrichAction) -> None:
    """Make a previewed new note resolvable by later batches without writing it."""
    assert action.new_note is not None
    frontmatter = yaml.safe_load(action.new_note.frontmatter_yaml) or {}
    frontmatter.setdefault("name", action.entity)
    frontmatter.setdefault("type", action.new_note.type)
    path = ROOT / action.target_note
    note = lint.Note(path=path, rel=action.target_note, fm=frontmatter, body="")
    for name in note.names() | {lint.resolve_key(action.entity)}:
        index.by_name[name] = note


def advance_planning_state(actions: list[EnrichAction], index: er.VaultIndex,
                           pending: er.PendingStore) -> None:
    """Apply only resolution-relevant effects to the in-memory preview state."""
    for action in actions:
        if action.action_type == "pending_fact":
            apply_pending_fact(pending, action)
        elif action.action_type == "new_note":
            pending.facts.pop(action.entity, None)
            add_virtual_note(index, action)


def request_actions(client, static_prompt: str, items_prompt: str,
                    model: str, effort: str) -> list[EnrichAction]:
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS_PER_BATCH,
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
            "format": {"type": "json_schema", "schema": EnrichResult.model_json_schema()},
        },
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    return normalize_actions(EnrichResult.model_validate_json(text))


# --------------------------------------------------------------------------- main

def run_preview(input_path: Path, dry_run: bool, model: str, effort: str,
                plan_path: Path | None = None,
                batch_size: int = DEFAULT_BATCH_SIZE,
                max_entities: int = DEFAULT_MAX_ENTITIES_PER_BATCH) -> int:
    items = load_triage_items(input_path)
    index = er.build_vault_index(ROOT)
    pending = er.load_pending_store()
    batches = make_batches(items, batch_size, index, max_entities)
    print(f"assembled {len(batches)} batch(es) for {len(items)} item(s), "
          f"batch_size<={batch_size}, entities<={max_entities}, "
          f"model={model}, effort={effort}")

    if dry_run:
        print("\n--- dry run: prompts below, no API call made ---")
        for number, batch in enumerate(batches, 1):
            print(f"\n--- batch {number}/{len(batches)} ({len(batch)} item(s)) ---\n")
            print(build_prompt(batch, index, pending))
        return 0

    client = tg.build_client()
    if client is None:
        print("No credentials found. Set ANTHROPIC_API_KEY, or ANTHROPIC_BASE_URL + "
              "ANTHROPIC_AUTH_TOKEN for a gateway. Source tools/.env first.",
              file=sys.stderr)
        return 1

    planning_pending = copy.deepcopy(pending)
    rejected_pairs = load_rejected_pairs()
    accepted: list[EnrichAction] = []
    rejected: list[Rejection] = []
    for number, batch in enumerate(batches, 1):
        print(f"\ncalling batch {number}/{len(batches)} ({len(batch)} item(s))...")
        static_prompt, items_prompt = build_prompt_parts(batch, index, planning_pending)
        actions = request_actions(client, static_prompt, items_prompt, model, effort)
        opinion_item_ids = {
            item.id for item in batch if item.development_type == "opinion"
        }
        batch_accepted, batch_rejected = validate_actions(
            actions, index, rejected_pairs, opinion_item_ids,
            resolution_map=build_resolution_map(batch, index, planning_pending),
            expected_item_ids={item.id for item in batch},
        )
        accepted.extend(batch_accepted)
        rejected.extend(batch_rejected)
        advance_planning_state(batch_accepted, index, planning_pending)

        print(f"batch {number}: {len(batch_accepted)} accepted, "
              f"{len(batch_rejected)} rejected")
        for action in batch_accepted:
            print(f"  {describe_action(action)}")
        for rejection in batch_rejected:
            print(f"  [REJECTED] {describe_action(rejection.action)} — {rejection.reason}")

    print(f"\nrun total: {len(accepted)} action(s) accepted, "
          f"{len(rejected)} rejected by hard guards")

    output_path = plan_path or default_plan_path(input_path)
    plan = build_plan(input_path, model, effort, accepted, rejected)
    try:
        write_plan(plan, output_path)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"\npreview complete — no vault content written")
    print(f"plan: {output_path}")
    if rejected:
        print(f"review required: plan records {len(rejected)} rejected proposal(s); "
              "they will not be applied")
    print(f"apply with: {sys.executable} tools/enrich.py --apply-plan {output_path}")
    return 0


def apply_saved_plan(plan_path: Path) -> int:
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError) as exc:
        print(f"cannot load plan {plan_path}: {exc}", file=sys.stderr)
        return 1

    problems = verify_plan_is_current(plan)
    if problems:
        print("plan is stale; no files written:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    pending = er.load_pending_store()
    for action in plan.actions:
        apply_action(action, pending)

    if any(action.action_type in ("pending_fact", "new_note")
           for action in plan.actions):
        er.save_pending_store(pending)

    paths = touched_paths(plan.actions)
    print(f"\napplied {len(plan.actions)} action(s) across {len(paths)} file(s)")

    lint_findings = lint.lint_vault(ROOT, only=paths)
    errors = [f for f in lint_findings if f.severity == lint.ERROR]
    if errors:
        print(f"\nLINT FAILED after apply — {len(errors)} error(s) on touched files:",
              file=sys.stderr)
        for f in errors:
            print(f.format(), file=sys.stderr)
        return 1

    print("lint: 0 errors on touched files")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path,
                        help="path to a Triage output JSON file")
    mode.add_argument("--apply-plan", type=Path,
                      help="apply an existing validated plan without an API call")
    parser.add_argument("--plan-out", type=Path,
                        help="preview artifact path (default: a timestamped file under "
                             "meta/review/enrich-plans/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the assembled prompt, make no API call")
    parser.add_argument("--model", default=tg.DEFAULT_MODEL)
    parser.add_argument("--effort", default=tg.DEFAULT_EFFORT,
                        choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"maximum items per API call (default: {DEFAULT_BATCH_SIZE}); "
                             "repeated unresolved entities force an earlier boundary")
    parser.add_argument("--max-entities", type=int, default=DEFAULT_MAX_ENTITIES_PER_BATCH,
                        help="maximum entity mentions per API call "
                             f"(default: {DEFAULT_MAX_ENTITIES_PER_BATCH})")
    args = parser.parse_args(argv)
    if args.apply_plan:
        if args.dry_run or args.plan_out:
            parser.error("--apply-plan cannot be combined with --dry-run or --plan-out")
        return apply_saved_plan(args.apply_plan)
    return run_preview(input_path=args.input, dry_run=args.dry_run,
                       model=args.model, effort=args.effort, plan_path=args.plan_out,
                       batch_size=args.batch_size, max_entities=args.max_entities)


if __name__ == "__main__":
    raise SystemExit(main())
