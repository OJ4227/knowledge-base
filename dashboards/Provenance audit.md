---
type: dashboard
name: Provenance audit
updated: 2026-08-30
---

# Provenance audit

Trust health of the vault. See [[DESIGN]] §8.

## Rumored claims

Timeline entries tagged `#claim/rumored` (material claim on a single tertiary source, or
otherwise unconfirmed).

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type"
FROM #claim/rumored
SORT file.name ASC
```

## Disputed claims

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type"
FROM #claim/disputed
SORT file.name ASC
```

## Source mix

```dataview
TABLE WITHOUT ID key AS "Tier", length(rows) AS "Sources"
FROM "sources"
WHERE type = "source"
GROUP BY tier
```

## Superseded / retracted sources

```dataview
TABLE WITHOUT ID file.link AS "Source", superseded_by AS "Superseded by"
FROM "sources"
WHERE type = "source" AND superseded_by
```

## Missing archives

Source notes with no `archive_url` — provenance is not yet durable.

```dataview
TABLE WITHOUT ID file.link AS "Source", publication AS "Publication", published AS "Published"
FROM "sources"
WHERE type = "source" AND !archive_url
SORT file.ctime DESC
```

> Uncited timeline bullets and frontmatter facts with no supporting citation are caught by
> the `lint` script, not here — see `meta/health/lint-report.md`.
