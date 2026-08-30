---
type: dashboard
name: Recently changed
updated: 2026-08-30
---

# Recently changed

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", updated AS "Updated", file.mtime AS "File modified"
FROM ""
WHERE type AND type != "dashboard" AND type != "meta" AND type != "source"
SORT file.mtime DESC
LIMIT 40
```

## New notes (last 30 days by `created`)

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", created AS "Created"
FROM ""
WHERE created AND date(created) >= date(today) - dur(30 days) AND type != "source"
SORT created DESC
```

## Sources ingested recently

```dataview
TABLE WITHOUT ID file.link AS "Source", publication AS "Publication", tier AS "Tier", published AS "Published"
FROM "sources"
WHERE type = "source"
SORT file.ctime DESC
LIMIT 25
```
