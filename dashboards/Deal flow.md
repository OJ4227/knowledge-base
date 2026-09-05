---
type: dashboard
name: Deal flow
updated: 2026-08-30
---

# Deal flow

Watchlist companies, for investment / partnership / scouting.

## High priority

```dataview
TABLE WITHOUT ID file.link AS "Company", stage AS "Stage", total_funding_usd AS "Raised (USD)", last_round.date AS "Last round", updated AS "Updated"
FROM "" AND -"templates"
WHERE type = "company" AND watchlist = true AND priority = "high"
SORT last_round.date DESC
```

## Early stage (seed / Series A) on the watchlist

```dataview
TABLE WITHOUT ID file.link AS "Company", stage AS "Stage", sectors AS "Sectors", last_round.date AS "Last round"
FROM "" AND -"templates"
WHERE type = "company" AND watchlist = true AND contains(list("seed", "series-a", "pre-seed"), stage)
SORT last_round.date DESC
```

## All watchlist companies

```dataview
TABLE WITHOUT ID file.link AS "Company", status AS "Status", stage AS "Stage", priority AS "Priority"
FROM "" AND -"templates"
WHERE type = "company" AND watchlist = true
SORT priority ASC, file.name ASC
```
