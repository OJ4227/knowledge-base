# Claude Code instructions

Read these files before discussing or changing the project:

1. `DESIGN.md` — accepted design and rationale
2. `HANDOVER.md` — current implementation state and next actions
3. `meta/ongoing-discussions.md` — unresolved design threads

For pipeline or vault-maintenance work, also follow `meta/agent-instructions.md`. Its
pipeline restrictions do not apply to owner-directed build and scaffolding work unless the
owner says otherwise.

## Preserve cross-session context

Before finishing a substantive response, update the repository context when the turn
changes any conclusion, evidence, alternative, uncertainty, implementation status,
blocker, or next step:

- Update `meta/ongoing-discussions.md` while a design question remains unresolved. Revise
  the existing topic; do not append a transcript or duplicate points.
- Update `DESIGN.md` when the owner explicitly accepts a durable design decision. Include
  enough rationale and consequences to avoid re-litigating it.
- Update `HANDOVER.md` when implementation state, verification, blockers, or the next
  concrete action changes.

Never treat Claude's recommendation as an accepted decision. Acceptance requires an
explicit owner decision or an implementation the owner requested.

When an ongoing discussion is decided and recorded in its permanent destination, remove
it from `meta/ongoing-discussions.md`. Keep unresolved alternatives and questions there.
Keep all context concise, factual, and safe to commit; never include credentials, secrets,
private prompts, or raw transcripts.

Project hooks check this obligation when a turn ends. Edits to the three context documents
are committed and pushed automatically. If synchronization fails, report that clearly and
leave the local change intact.

## Working rules

- Do not claim a command or test passed unless it was run successfully.
- Do not force-push or resolve Git conflicts automatically.
- Do not stage unrelated files when maintaining context.
- Keep commits small and messages short.
