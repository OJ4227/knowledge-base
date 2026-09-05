---
type: concept
name: "Model routing"
aliases: [model router, LLM routing, model selection]
category: pattern
related: []
maturity: emerging
created: 2026-08-30
updated: 2026-08-30
---

# Model routing

<!-- curated: this whole note is owner-curated. Agents draft and propose, never edit in place. -->
<!-- related: [] is intentional. The natural neighbours — [[LLM gateway]] and
     [[Inference parameters]] — aren't written yet; the body links are markers. -->

## Definition

Deciding *which* model, provider, or model tier should handle a given request, instead of
sending everything to one model. Ranges from a fixed rule to a learned classifier that
predicts the cheapest model likely to answer a request well.

## How it works

Common strategies, roughly increasing in sophistication:

- **Static / rule-based** — route on hard signals: request type, endpoint, user tier,
  prompt length, whether an image is attached, which customer. "Code → model A, chat →
  model B."
- **Classifier-based** — a small fast model scores each request's difficulty or category
  and picks a model to match, trained on data of the form *(prompt → which model
  succeeded)*.
- **Cascading / fallback** — send to a cheap model first; if its answer fails a check (low
  confidence, a verifier rejects it, a schema doesn't validate), escalate to a stronger
  model. Pay the expensive-model cost only when it's needed.
- **Load balancing** — spread requests across providers or regions for rate-limit headroom
  and redundancy, with no quality difference intended.

Every routing decision trades three things against each other: answer quality, cost per
request, and latency.

## Why it matters

Frontier models cost 10–100× what small ones do, and most real traffic is easy. Routing is
the main lever for cutting inference spend without a visible drop in quality. It also
decouples the application from any single model or vendor, which helps with resilience and
with adopting new models as they ship.

## Variants / alternatives

- **One model + parameter tuning** — just pick a mid-tier model and adjust
  [[Inference parameters]]. Simpler, no routing infrastructure, leaves the savings on the
  table.
- **Step-level routing** — route the individual steps of one agent or chain to different
  models (a small planner, a strong executor) rather than routing whole requests.
- **Provider "auto" endpoints** — some labs expose a single endpoint that routes internally
  across their own model sizes and reasoning levels; you outsource the decision.

## Related concepts

- [[LLM gateway]] — the software layer where routing rules are usually configured *(not yet written)*
- [[Inference parameters]] — the per-request knobs on whichever model is chosen *(not yet written)*

## Sources

- Ong et al., "RouteLLM: Learning to Route LLMs with Preference Data", 2024 — <https://arxiv.org/abs/2406.18665>
- Also widely practised without a formal method — static rules in application code are the common baseline.
