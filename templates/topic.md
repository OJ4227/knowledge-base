---
type: moc
name: "<note name>"
aliases: []
kind: thread          # thread (running narrative) | index (pure MOC)
domains: []            # ai | robotics | hardware/compute | business
concepts: []           # [[concepts/...]] this thread is about
related: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <note name>

<!-- curated intro: what this thread tracks and why it matters -->

## Current state

<!-- gardener-maintained: the one paragraph to read to be caught up -->

## Timeline

<!-- Append-only. Newest first. Developments linked to their entity + source. -->

### YYYY

-

## Key entities

```dataview
LIST
FROM "" AND -"templates" AND -"meta"
WHERE contains(file.outlinks, this.file.link) AND type != "source"
SORT file.name ASC
```

## Key links
