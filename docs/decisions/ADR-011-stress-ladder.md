# ADR-011: Stress ladder at 10 / 20 / 50%

**Date:** 2026-11-24

## Context

Convexity needs a fixed structural probe: how does deliverable flow respond as shock intensity grows? A continuous curve invites fitting and prediction. A short discrete ladder is enough to see whether losses accelerate, stay linear, or decelerate.

## Decision

Use a stress ladder at **10%, 20%, and 50%** loss intensities (\(\delta \in \{0.10, 0.20, 0.50\}\)).

**Convexity** is loss acceleration across that ladder:

- **Concave** payoff (losses accelerate) → fragile
- **Linear** → robust
- **Convex** payoff (losses decelerate) → antifragile

This is a property of the graph's flow response under the ladder, not a forecast of which shock arrives.

## Status

Accepted (ruin probe). Convexity *classification* from this ladder is superseded by [ADR-015](ADR-015-convexity-distance-to-ruin-not-tested.md) (symmetric second differences on model output, anchored on worst-on-record).

## Consequences

- Ladder constant: `STRESS_LADDER = (0.10, 0.20, 0.50)` in `metrics/thresholds.py`; shared helpers in `metrics/stress.py`.
- `metrics/ruin.py` reuses the same ladder when an **explicit** probe is configured ([ADR-009](ADR-009-ruin-hard-red-flag.md), [ADR-015](ADR-015-convexity-distance-to-ruin-not-tested.md)).
- Convexity no longer classifies shape from the 10/20/50 ladder alone; see ADR-015.

## Alternatives rejected

- **Dense / continuous stress curves with fitted parameters** — prediction-flavoured and harder to golden-test.
- **Single shock intensity** — cannot distinguish accelerating vs decelerating loss.
