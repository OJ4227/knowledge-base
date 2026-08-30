---
type: dashboard
name: Stale watchlist
updated: 2026-08-30
---

# Stale watchlist

Watchlist companies with no update in a while — either genuinely quiet, or the pipeline is
missing them. Review periodically.

```dataview
TABLE WITHOUT ID file.link AS "Company", priority AS "Priority", updated AS "Last updated", (date(today) - date(updated)).days AS "Days stale"
FROM ""
WHERE type = "company" AND watchlist = true AND updated AND date(updated) < date(today) - dur(90 days)
SORT updated ASC
```

## Threads gone quiet (no update in 60 days)

```dataview
TABLE WITHOUT ID file.link AS "Thread", updated AS "Last updated"
FROM ""
WHERE type = "moc" AND kind = "thread" AND updated AND date(updated) < date(today) - dur(60 days)
SORT updated ASC
```
