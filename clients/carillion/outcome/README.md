# Carillion outcome reference list

Procedure-defined **outcome reference list** for structural-weakness scoring of
the locked Carillion map, per
[ADR-020](../../../docs/decisions/ADR-020-backtest-scoring.md).

**This folder is the reference list only.** Scoring results live in
[docs/backtests/carillion-scoring-result.md](../../../docs/backtests/carillion-scoring-result.md)
(draft; pending Miles’s review per ADR-020).

## Blinding rule (this PR)

While building this list, the author did **not** open, read, or grep anything
under `clients/carillion/maps/`, and did **not** run `run_all` (or any metric
compute) on the Carillion model. Mapping uses model **entity IDs** from
`model/carillion.yaml` and published metric names only — not locked-map status.

## Contents

| File | Role |
|---|---|
| `sources.yaml` | Authoritative **post-event** public sources (title, publisher, date, URL) |
| `reference_list.yaml` | Structural weaknesses **named by those sources** as causal or contributing, with metric/driver mapping, judgement log, and notable exclusions |

## Rules (ADR-020)

- Source classes: parliamentary / select-committee reports, Official Receiver or
  Insolvency Service material, regulator or enforcement findings, and similarly
  primary official inquiries. Secondary journalism is out of scope.
- Extraction: each item is a weakness the **source** names as causal or
  contributing — not an inferred hindsight narrative.
- Mapping: every item maps to Aegis metric(s) and a driver entity (model ID), or
  to `not_representable` (method gap) with a reason.
- No prediction language; no blended score; no edits to model, map, metrics,
  thresholds, schemas, or eval baselines.

## Scoring

Driver-level comparison of the locked map (`method_tag: carillion-method-v1`)
to this list is recorded in
[docs/backtests/carillion-scoring-result.md](../../../docs/backtests/carillion-scoring-result.md).
