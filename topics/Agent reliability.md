---
type: moc
name: "Agent reliability"
aliases: []
kind: thread
domains: [ai]
concepts: ["[[Function calling]]", "[[Model Context Protocol]]"]
related: []
created: 2026-08-30
updated: 2026-08-30
---

# Agent reliability

<!-- curated intro -->

Tracks the gap between impressive agent demos and agents dependable enough to run
unattended in production. The recurring failure mode: small per-step error rates compound
over long task horizons, and evaluation is hard because failures are diffuse and
context-dependent.

## Current state

<!-- gardener-maintained: the one paragraph to read to be caught up -->

As of mid-2026, reliability is still the main blocker to broadly autonomous agents. The
working pattern in production is narrow task scopes, explicit verification or critic steps,
and human checkpoints on consequential actions. Progress is coming from stronger base
models, better tool-use post-training (fewer malformed [[Function calling]] arguments), and
standardised tooling via the [[Model Context Protocol]]. [[Anysphere]] (autonomous coding
agents) and [[Anthropic]] are useful bellwethers.

## Timeline

### 2024

- 2024-11-25 — [[Anthropic]] released the [[Model Context Protocol]], standardising how agents connect to tools and data. ([[sources/2024-11-25-anthropic-mcp-announcement]]) #milestone

## Key entities

```dataview
LIST
FROM "" AND -"templates" AND -"meta"
WHERE contains(file.outlinks, this.file.link) AND type != "source"
SORT file.name ASC
```

## Key links

-
