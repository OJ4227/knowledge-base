---
type: moc
name: "<% tp.file.title %>"
aliases: []
kind: thread          # thread (running narrative) | index (pure MOC)
domains: []            # ai | robotics | hardware/compute | business
concepts: []           # [[concepts/...]] this thread is about
related: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# <% tp.file.title %>

<!-- curated intro: what this thread tracks and why it matters -->

## Current state

<!-- gardener-maintained: the one paragraph to read to be caught up -->

## Timeline

<!-- Append-only. Newest first. Developments linked to their entity + source. -->

### <% tp.date.now("YYYY") %>

-

## Key entities

```dataview
LIST
FROM ""
WHERE contains(file.outlinks, this.file.link) AND type != "source"
SORT file.name ASC
```

## Key links
