---
type: dashboard
name: Home
updated: 2026-08-30
---

# Knowledge Base — Home

Design: [[DESIGN]] · Schemas: [[schema]] · Taxonomy: [[taxonomy]] · Agent rules: [[agent-instructions]] · Sources: [[sources]]

## Dashboards

- [[Deal flow]] — watchlist companies by priority and stage
- [[Recently changed]] — what the pipeline touched lately
- [[Stale watchlist]] — tracked companies going quiet
- [[Provenance audit]] — rumored / disputed / thinly-sourced claims
- [[Concepts index]] — the evergreen reference layer
- [[Threads]] — running narratives
- [[This week]] — latest digest

## Counts

```dataview
TABLE WITHOUT ID type AS "Type", length(rows) AS "Notes"
FROM ""
WHERE type
GROUP BY type
SORT length(rows) DESC
```

## Recently updated (any type)

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", updated AS "Updated"
FROM ""
WHERE updated AND type != "dashboard" AND type != "meta"
SORT updated DESC
LIMIT 15
```
