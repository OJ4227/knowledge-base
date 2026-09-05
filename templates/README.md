---
type: meta
name: Templates
updated: 2026-09-05
---

# templates/

Canonical structure for each note `type` in [[schema]]. These are **static skeletons** —
plain placeholder text (`<note name>`, `YYYY-MM-DD`), no template-engine syntax.

Claude and the pipeline agents copy this structure when creating a note. To make one by
hand, duplicate the file into the right folder, rename it, and fill it in.

| Template | For |
|---|---|
| `concept.md` | `concepts/` — evergreen explainers |
| `company.md` | `companies/` |
| `person.md` | `people/` |
| `technology.md` | `technologies/` — tracked models / hardware / robots / frameworks / benchmarks |
| `topic.md` | `topics/` — threads and MOCs |
| `source.md` | `sources/` — provenance notes |

If you change a template, change [[schema]] and the `lint` rules in the same commit.

Dataview excludes `templates/` from its queries (the files carry real `type:` values), so
these skeletons never show up as notes in dashboards.
