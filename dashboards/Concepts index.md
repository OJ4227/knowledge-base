---
type: dashboard
name: Concepts index
updated: 2026-08-30
---

# Concepts index

The evergreen reference layer — how modern AI / LLM / robotics systems work.

## By category

```dataview
TABLE WITHOUT ID file.link AS "Concept", maturity AS "Maturity", updated AS "Updated"
FROM "concepts"
WHERE type = "concept"
GROUP BY category
SORT category ASC
```

## Contested or fading — may need a refresh

```dataview
TABLE WITHOUT ID file.link AS "Concept", maturity AS "Maturity", updated AS "Updated"
FROM "concepts"
WHERE type = "concept" AND contains(list("contested", "fading"), maturity)
SORT updated ASC
```

## Stubs — thin concept notes needing work

```dataview
TABLE WITHOUT ID file.link AS "Concept", file.size AS "Bytes"
FROM "concepts"
WHERE type = "concept" AND file.size < 800
SORT file.size ASC
```
