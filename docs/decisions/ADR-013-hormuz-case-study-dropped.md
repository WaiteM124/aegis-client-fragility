# ADR-013: Strait of Hormuz case study dropped

**Date:** 2026-11-22 – 2026-11-23

## Context

A Strait of Hormuz closure case study was drafted as a flagship narrative: pick a vivid geopolitical shock, pre-register an event set, and show how Aegis would have scored clients. That looks like product validation. In practice it rewards forecasting skill on a known story and pulls copy and metrics toward "would we have predicted this?"

## Decision

The Hormuz closure case study was **chosen and then dropped**.

Do not use a pre-registered event backtest as the product's proof. Validation belongs on structural metrics and known-answer graphs ([ADR-006](ADR-006-no-prediction.md)), not on whether the system would have called a historical headline.

## Status

Accepted

## Consequences

- Marketing and eval design should stress structural weakness discovery (toy / YAML graphs, group statuses, ruin flags), not event-prediction retrospectives.
- Live events remain valid as **stressors** mapped onto a client graph ([ADR-005](ADR-005-product-positioning.md)); they are not the yardstick for whether Aegis "works".
- No Hormuz-specific fixtures or backtest harness should be added under that framing.
- A **public historical pack** (e.g. Carillion) may still be scored for structural-weakness detection against a procedure-defined outcome reference list — driver-level hits/misses/method gaps/false flags, no prediction claim. That use is defined in [ADR-020](ADR-020-backtest-scoring.md); it is not an event-prediction proof and does not weaken this ADR.

## Alternatives rejected

- **Keep Hormuz as a pre-registered event backtest** — prediction-flavoured validation; conflicts with ADR-006.
- **Replace Hormuz with another single historical shock backtest** — same failure mode under a different name.
