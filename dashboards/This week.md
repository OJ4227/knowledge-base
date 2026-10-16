---
type: dashboard
name: This week
updated: 2026-08-30
---

# This week

## Latest daily digests

```dataview
TABLE WITHOUT ID file.link AS "Digest", file.mtime AS "Generated"
FROM "digests"
WHERE file.name =~ "^\d{4}-\d{2}-\d{2}$"
SORT file.name DESC
LIMIT 7
```

## Latest weekly digests

```dataview
TABLE WITHOUT ID file.link AS "Digest", file.mtime AS "Generated"
FROM "digests"
WHERE file.name =~ "^\d{4}-W\d{2}$"
SORT file.name DESC
LIMIT 4
```

## Open review items

```dataview
TABLE WITHOUT ID file.link AS "Review file", file.mtime AS "Updated"
FROM "meta/review"
WHERE file.name != "README"
SORT file.name DESC
```

## Latest health report

Generated files, not versioned — open from the file tree under `meta/health/`:

- `meta/health/report.md` — regenerated weekly by the gardener
- `meta/health/lint-report.md` — regenerated every run of `tools/lint.py`
