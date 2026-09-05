---
type: concept
name: "Model Context Protocol"
aliases: [MCP]
category: protocol
related: ["[[Function calling]]"]
maturity: established
created: 2026-08-30
updated: 2026-08-30
---

# Model Context Protocol

<!-- curated: this whole note is owner-curated. Agents draft and propose, never edit in place. -->

## Definition

An open protocol that standardises how AI applications connect to external tools, data
sources, and prompts. Introduced by [[Anthropic]] in November 2024 and subsequently adopted
across the industry. Often described as "a USB-C port for AI applications" — one connector
instead of a bespoke integration per tool.

## How it works

A client–server architecture:

- **Host** — the AI application (an IDE, a chat client, an agent runtime).
- **Client** — lives inside the host, holds one connection per server.
- **Server** — a small program exposing capabilities in three categories:
  - **Tools** — functions the model can call (side effects allowed).
  - **Resources** — read-only data the host can pull into context (files, records).
  - **Prompts** — reusable templated interactions.

Transport is JSON-RPC 2.0 over either stdio (local subprocess) or streamable HTTP (remote).
The host connects to a server, asks what it exposes, and forwards those tool definitions to
the model at request time — see [[Function calling]] for what happens model-side.

## Why it matters

Before MCP, every application–tool pairing was a custom integration — an N×M problem. MCP
turns it into N+M: any MCP-compatible host can use any MCP server. This is the substrate
that makes portable, composable agent tooling possible, and its rapid cross-vendor adoption
through 2025 made it a de facto standard rather than a single vendor's format.

## Variants / alternatives

- **Framework-specific tool registries** — e.g. LangChain tools; predate MCP and
  increasingly wrap it rather than compete with it.
- **OpenAI plugins** (deprecated) — an earlier, narrower attempt at exposing external
  capabilities to a model.
- **Bespoke per-app integrations** — the status quo MCP replaces.

## Related concepts

- [[Function calling]] — the model-side primitive MCP packages and transports.

## Developments

Tracked in [[Agent reliability]].

## Sources

- Anthropic, "Introducing the Model Context Protocol", 2024-11-25 — <https://www.anthropic.com/news/model-context-protocol>
- MCP specification and documentation — <https://modelcontextprotocol.io>
