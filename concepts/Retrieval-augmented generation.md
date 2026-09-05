---
type: concept
name: "Retrieval-augmented generation"
aliases: [RAG]
category: technique
related: []
maturity: established
created: 2026-08-30
updated: 2026-08-30
---

# Retrieval-augmented generation

<!-- curated: this whole note is owner-curated. Agents draft and propose, never edit in place. -->
<!-- related: [] is intentional — no close concept-peer in the vault yet. -->

## Definition

An architecture pattern that combines a **retrieval** step — fetch text relevant to the
query from an external corpus — with a **generation** step — have a language model write
its answer conditioned on that retrieved text. Introduced by Lewis et al. (2020).

## How it works

1. **Index** the corpus offline: split documents into chunks, convert each chunk to a
   vector embedding, store the vectors in a search index (often alongside a keyword index).
2. **Retrieve** at query time: embed the user's query, pull the top-k most similar chunks,
   optionally re-rank them with a more expensive model.
3. **Augment**: build the model's prompt with the retrieved chunks inserted as context.
4. **Generate**: the model answers from that context, ideally citing which chunks it used.

## Why it matters

Lets a model draw on fresh, private, or domain-specific knowledge without retraining it;
reduces hallucination by grounding answers in real passages; and gives provenance for what
the model says. It is the default architecture for enterprise LLM applications.

## Variants / alternatives

- **Naive vs advanced RAG** — query rewriting, hybrid (keyword + vector) search,
  re-ranking, multi-hop retrieval.
- **GraphRAG** — retrieve over a knowledge graph instead of a flat chunk store.
- **Agentic RAG** — an agent decides what to retrieve and when, iteratively, rather than a
  single fixed retrieve-then-generate pass.
- **Long-context prompting** — as context windows grow, sometimes you can skip retrieval
  and put the whole corpus in the prompt. Complement and partial competitor.
- **Fine-tuning** — bake the knowledge into the weights. Higher cost, goes stale, no
  provenance.

## Related concepts

_(none in this vault yet)_

## Sources

- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", 2020 — <https://arxiv.org/abs/2005.11401>
