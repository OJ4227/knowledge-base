---
type: dashboard
name: This week
updated: 2026-08-30
---

# This week

## Latest digests

```dataview
TABLE WITHOUT ID file.link AS "Digest", file.mtime AS "Generated"
FROM "digests"
SORT file.name DESC
LIMIT 8
```

## Open review items

```dataview
TABLE WITHOUT ID file.link AS "Review file", file.mtime AS "Updated"
FROM "meta/review"
WHERE file.name != "README"
SORT file.name DESC
```

## Latest health report

- [[report]] (in `meta/health/`) — regenerated weekly by the gardener
- [[lint-report]] (in `meta/health/`) — regenerated every run by the lint script
