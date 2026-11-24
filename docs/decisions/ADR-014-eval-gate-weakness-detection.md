# ADR-014: Eval gate measures weakness detection, not prediction

**Date:** 2026-11-24

## Context

Aegis finds structural weaknesses in client dependency graphs (concentration, contagion, convexity, optionality). It does **not** predict which shock will arrive, estimate event probabilities, or fit historical tails ([ADR-006](ADR-006-no-prediction.md)).

The metrics package is deterministic and unit-tested, but unit tests alone do not guard against silent regressions in *detection*: a metric that stops flagging a known monoculture, hidden SPOF, deep cascade, concave ladder, or ruin condition, or that starts painting a well-diversified robust graph red.

We needed a CI gate that:

1. Uses labelled synthetic graphs with known ground-truth weaknesses.
2. Measures detection quality without introducing predictive framing.
3. Fails the build when detection regresses relative to a committed baseline.

## Decision

Add a deterministic eval suite under `evals/` and a CI job `eval-gate` that runs on every pull request and push to `master`/`main`.

The suite measures:

| Signal | Meaning |
|---|---|
| Per-metric **detection recall** | Among cases that label a metric as a detector for a known weakness, the fraction where that metric returns amber or red. |
| Per-metric **false-flag rate** on controls | Among robust control graphs, the fraction where the metric returns **red**. |
| **Group-status accuracy** | Worst-member group status (`Concentration`, `Contagion`, `Convexity`, `Optionality`) matches the labelled expectation. |
| **Hard control rule** | Any robust control flagged **red** on any metric fails the gate. |

Results go to `evals/results.json`. The regression floor is `evals/baseline.json`. CI fails if any metric’s recall or group accuracy drops below the baseline, or if any robust control is flagged red.

The suite deliberately does **not** measure event likelihood, severity forecasts, “probability of ruin”, historical-correlation / fitted-tail quality, or a blended fragility score across groups. Ruin remains a hard red flag in group roll-up ([ADR-009](ADR-009-ruin-hard-red-flag.md)); the gate does not average it away.

Existing pytest tests marked `evaluation` (assessment quality baselines and model-comparison with a stub Gemini client) run offline with no API keys. The `eval-gate` job also runs `pytest -m evaluation` so those behavioural checks stay on the critical path without secrets. Live-model evaluation, if added later, stays out of this job.

## Status

Accepted

## Consequences

- Every PR exercises structural weakness detection on 20–40 labelled graphs via `evals/run_evals.py` and `make eval-gate`.
- Baseline bumps require an intentional commit when detection expectations change for justified reasons — not to paper over a metric bug.
- Metric formula bugs discovered by the suite are fixed in a **separate commit** from eval harness / case changes, so review can separate cause and detection.
- Docs and UI copy must continue to avoid predictive framing; the ADR title is the standing reminder that the gate measures **flags**, not forecasts.
- Related: [ADR-006](ADR-006-no-prediction.md), [ADR-008](ADR-008-no-blended-fragility-score.md), [ADR-009](ADR-009-ruin-hard-red-flag.md), [ADR-011](ADR-011-stress-ladder.md).

## Alternatives rejected

- **Forecast-quality gate** (Brier score, calibration, backtest hit rate) — pulls the product toward prediction and contradicts ADR-006.
- **Single blended fragility accuracy number** — would hide group-level failures and softens ruin ([ADR-008](ADR-008-no-blended-fragility-score.md), [ADR-009](ADR-009-ruin-hard-red-flag.md)).
- **Live-model-only eval job** — needs API keys and is slower; offline labelled graphs + stub providers are sufficient for a PR gate.
