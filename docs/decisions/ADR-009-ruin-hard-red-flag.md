# ADR-009: Ruin is a hard red flag

**Date:** 2026-11-24

## Context

Some stress responses deplete deliverable flow past a point of no return. That condition must remain visible. If ruin can be averaged into a milder score, operators will miss the structural cliff.

## Decision

**Ruin is a hard red flag.** It cannot be averaged away.

A client is in ruin when, on any rung of the stress ladder:

\[
F(\delta) < \textit{survival\_floor} \times F_0
\]

where \(F_0\) is baseline deliverable inbound flow and \(F(\delta)\) is remaining flow after structural stress at intensity \(\delta\).

- Default **survival floor = 0.5** (strict inequality: remaining exactly at the floor is not ruin).
- Configurable per graph in YAML (`survival_floor`) or via CLI `--survival-floor` (scenario override wins).

## Status

Accepted

## Consequences

- Implemented in `metrics/ruin.py` and `metrics/thresholds.py` (`RuinThresholds.survival_floor = 0.5`). Resolution order: scenario / `--survival-floor` → graph YAML → default.
- `metrics/run_all.py` forces the Convexity group to red when ruin is red.
- Related: stress ladder intensities in [ADR-011](ADR-011-stress-ladder.md).

## Alternatives rejected

- **Floor of 0 (total loss only)** — too lax; a client is usually finished well before complete wipe-out.
- **Soft / amber ruin that can be blended** — contradicts the hard-flag requirement in [ADR-008](ADR-008-no-blended-fragility-score.md).
