---
type: concept
name: "Function calling"
aliases: [Tool use, tool calling]
category: primitive
related: ["[[Model Context Protocol]]"]
maturity: established
created: 2026-08-30
updated: 2026-08-30
---

# Function calling

<!-- curated: this whole note is owner-curated. Agents draft and propose, never edit in place. -->

## Definition

The capability of a language model to emit a structured request to invoke an external
function — given a machine-readable description of the functions available — instead of
answering in prose. The application executes the function and returns the result to the
model, which continues from there. Also called *tool use* or *tool calling*.

## How it works

1. **The application supplies the tool list.** With each request, the application sends the
   model a list of function definitions — for each, a name, a description, and a JSON
   Schema for its parameters. The model can only call what is in this list; it never
   discovers tools on its own. The entries may be hand-written by the application
   developer (each a thin wrapper around an internal function, a third-party API, or a
   database query), or collected from an [[Model Context Protocol]] server or framework
   registry the developer has connected. Either way the application assembles the list and
   sends it.
2. During generation the model decides a function is needed and outputs a structured call
   (function name + argument values) rather than text.
3. The application runs the corresponding code and appends the result to the conversation.
4. The model reads the result and either calls another function, or answers.

Modern APIs support several calls in one turn and can force the model to call a specific
tool. Models acquire the behaviour through post-training on tool-use examples; constructing
valid arguments reliably is a known weak point (see [[Agent reliability]]).

## Why it matters

This is the primitive underneath almost everything an LLM does beyond producing text —
agents, retrieval orchestration, application integrations, computer use. If the model
picks the wrong tool or malforms the arguments, the whole chain above it fails.

## Variants / alternatives

- **ReAct-style prompting** — the model reasons and names actions in prose, which the
  application parses out. The pattern used before model APIs supported this natively;
  still a fallback for models that do not.
- **Constrained decoding (a.k.a. structured outputs)** — a model generates text one token
  at a time; constrained decoding blocks, at each step, any token that would break the
  required JSON shape, so the model can only produce output that matches the schema. This
  makes a well-formed call *guaranteed* rather than dependent on the model complying.
- **Code as action (CodeAct)** — instead of emitting discrete JSON calls, the model writes
  a snippet of code that calls the tools. More expressive, harder to sandbox safely.

## Related concepts

- [[Model Context Protocol]] — a standard for packaging and transporting tools that are
  built on this primitive.

## Sources

- OpenAI, "Function calling and other API updates", 2023-06-13 — <https://openai.com/index/function-calling-and-other-api-updates/>
- Anthropic, "Tool use" documentation — <https://docs.anthropic.com/en/docs/build-with-claude/tool-use>
- Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models", 2022 — <https://arxiv.org/abs/2210.03629>
