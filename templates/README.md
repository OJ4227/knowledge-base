---
type: meta
name: Templates
updated: 2026-08-30
---

# templates/

Note templates, one per `type` in [[schema]]. They use [Templater](https://silentvoid13.github.io/Templater/)
syntax (`<% tp.* %>`) — set Templater's template folder to `templates/` after installing.

| Template | For |
|---|---|
| `concept.md` | `concepts/` — evergreen explainers |
| `company.md` | `companies/` |
| `person.md` | `people/` |
| `technology.md` | `technologies/` — tracked models / hardware / robots / frameworks / benchmarks |
| `topic.md` | `topics/` — threads and MOCs |
| `source.md` | `sources/` — provenance notes |

If you change a template, change [[schema]] and the `lint` rules in the same commit.
