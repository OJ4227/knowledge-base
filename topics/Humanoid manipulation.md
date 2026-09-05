---
type: moc
name: "Humanoid manipulation"
aliases: []
kind: thread
domains: [robotics]
concepts: []
related: []
created: 2026-08-30
updated: 2026-08-30
---

# Humanoid manipulation

<!-- curated intro -->

Tracks progress in dexterous, general-purpose manipulation for humanoid robots — the
hands-and-arms problem, as distinct from locomotion. The hard parts: contact-rich tasks,
generalising across objects and environments, and doing it fast enough to be useful.

## Current state

<!-- gardener-maintained: the one paragraph to read to be caught up -->

The dominant approach is learning-based control, increasingly via vision-language-action
(VLA) models that map camera frames and a language instruction directly to motor commands.
The binding constraint is training data: teleoperation demonstrations are expensive, and
simulation and internet video are only partial substitutes. Whole-body manipulation —
using legs and torso to brace and extend reach — is an active frontier. [[Figure AI]] is a
leading commercial effort.

## Timeline

<!-- seed: no cited entries yet -->

### 2026

-

## Key entities

```dataview
LIST
FROM "" AND -"templates" AND -"meta"
WHERE contains(file.outlinks, this.file.link) AND type != "source"
SORT file.name ASC
```

## Key links

-
