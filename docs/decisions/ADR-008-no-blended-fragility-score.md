# ADR-008: No blended fragility score — four metric groups

**Date:** 2026-11-24

## Context

A single weighted "fragility score" is easy to put on a dashboard and hard to trust. Different metrics have different units and meanings; averaging them hides danger (especially ruin) and invents a precision the maths does not have.

## Decision

**No blended or weighted single fragility score.**

Report four groups. Each group shows its **worst** member metric's red / amber / green status:

| Group | Member metrics |
|---|---|
| **Concentration** | HHI, monoculture, hub dominance |
| **Contagion** | Hidden coupling, single points of failure, cascade depth |
| **Convexity** | Taleb heuristic / Jensen gap, stress ladder, ruin |
| **Optionality** | Optionality, slack, recovery time |

## Status

Accepted

## Consequences

- `metrics/run_all.py` groups results and takes the worst status per group (`worst_status`). Ruin forces the Convexity group red ([ADR-009](ADR-009-ruin-hard-red-flag.md)).
- Implemented today under `metrics/`: HHI, monoculture; SPOF, cascade depth; convexity (stress-ladder acceleration + Jensen gap), ruin; optionality, slack. **Hub dominance**, **hidden coupling**, and **recovery time** are decided members not yet present as modules — add them as one-file metrics ([ADR-010](ADR-010-one-file-per-metric.md)), do not invent a blend to paper over the gap.
- UI and APIs must expose group statuses (and member detail), never a single cross-group fragility number.

## Alternatives rejected

- **Weighted blend across groups** — conceals red flags and mixes incompatible units.
- **Single composite index for executive dashboards** — same problem with a friendlier name.
