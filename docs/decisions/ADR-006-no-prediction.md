# ADR-006: Aegis never predicts

**Date:** 2026-11-24

## Context

Risk tools often sell forecasts: event probabilities, fitted tails, expected shortfall, Kelly-style sizing. Those are prediction problems. Aegis's claim is different: find structural weaknesses that matter **whatever** shock arrives. Mixing prediction maths into metrics would make validation about forecasting skill instead of whether weaknesses are correctly flagged.

## Decision

Aegis **never predicts**. It finds structural weaknesses regardless of which shock comes.

Validation is whether metrics correctly flag real structural weaknesses on known graphs — not whether the system forecasts events, losses, or probabilities.

## Status

Accepted

## Consequences

- Metrics in `metrics/` must stay structural probes (shares, path counts, stress-ladder flow response). No forecasting, fitted distributions, historical-correlation estimates, or predictive copy in docs/API/UI (avoid "likely", "will happen", "probability of X").
- Package docstring and module docs already state this boundary (`metrics/__init__.py`, metric module headers).
- Related: [ADR-013](ADR-013-hormuz-case-study-dropped.md) (event backtests pull toward prediction).

## Alternatives rejected

- **Tail index** — estimates how heavy the loss tail is; a forecasting-flavoured statistic.
- **Expected shortfall** — a predictive loss measure conditional on a tail threshold.
- **Kelly criterion / Kelly-style sizing** — optimal bet sizing under a probabilistic model; out of scope for structural fragility.
