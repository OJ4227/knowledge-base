---
type: dashboard
name: Threads
updated: 2026-08-30
---

# Threads

Running narratives. Open one to catch up on a subject top-down.

```dataview
TABLE WITHOUT ID file.link AS "Thread", domains AS "Domains", updated AS "Last updated"
FROM "" AND -"templates"
WHERE type = "moc" AND kind = "thread"
SORT updated DESC
```

## Pure indexes / MOCs

```dataview
TABLE WITHOUT ID file.link AS "MOC", updated AS "Updated"
FROM "" AND -"templates"
WHERE type = "moc" AND kind = "index"
SORT file.name ASC
```
