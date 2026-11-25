# Carillion backtest — method freeze (`carillion-method-v1`)

This document defines what is frozen for the Carillion plc public backtest.
It does **not** forecast insolvency or any event. Scoring of the locked map
against post-event structural weaknesses follows
[ADR-020](../decisions/ADR-020-backtest-scoring.md) (Proposed): driver-level
categories (hit-from-evidence, hit-from-unknown, miss, method gap, false flag),
no blended score, no prediction claim. The freeze itself does not perform that
comparison.

## Freeze tag

| Item | Value |
|---|---|
| Tag | `carillion-method-v1` |
| Created on | the **merge commit** of the PR that committed the approved source pack and this freeze note |
| Who tags | the maintainer (agents do **not** create the tag) |

Any later change to metric logic, thresholds, or the eval floor that would
alter Carillion readings must **not** be applied to this backtest without a
**new** method tag (e.g. `carillion-method-v2`) and a documented reason.

## What the freeze covers

### Metric modules and versions

Top-level modules under `metrics/*.py` that implement `compute` (and shared
helpers they import). Versions at freeze (module `VERSION` constants):

| Metric | Module | Version |
|---|---|---|
| HHI | `metrics/hhi.py` | 1.0.0 |
| Monoculture | `metrics/monoculture.py` | 1.0.0 |
| Customer HHI | `metrics/customer_hhi.py` | 1.0.0 |
| Customer monoculture | `metrics/customer_monoculture.py` | 1.0.0 |
| Single points of failure | `metrics/single_points_of_failure.py` | 2.0.0 |
| Cascade depth | `metrics/cascade_depth.py` | 1.0.0 |
| Customer SPOF | `metrics/customer_spof.py` | 1.0.0 |
| Convexity | `metrics/convexity.py` | 2.1.0 |
| Ruin | `metrics/ruin.py` | 3.0.0 |
| Distance to ruin | `metrics/distance_to_ruin.py` | 2.0.0 |
| Runway | `metrics/runway.py` | 1.0.0 |
| Energy margin | `metrics/energy_margin.py` | 1.0.0 |
| Optionality | `metrics/optionality.py` | 2.0.0 |
| Slack | `metrics/slack.py` | 1.0.0 |

Shared code on the freeze surface (also under `metrics/*.py`): `contracts.py`,
`finance.py`, `graph_loader.py`, `stress.py`, `cli_utils.py`, `run_all.py`
(group registration / worst-member roll-up), `run_record.py`, `client_pack.py`,
and package `__init__.py`.

### Thresholds

`metrics/thresholds.py` — all default status cut-points, stress-ladder
defaults, survival floor, runway / energy-margin / distance-to-ruin cut-offs,
and related versioned threshold dataclasses.

### Eval baseline

`evals/baseline.json` — regression floor for weakness detection (recall,
false-flag rate, group-status accuracy). Not a forecast-quality target.

### Schemas

- `metrics/schemas/run_record.v1.json`
- `metrics/schemas/run_record.v2.json` (includes optional `method_tag`)
- `clients/schemas/client.v1.json`
- `clients/schemas/sources_manifest.v1.json`
- `clients/schemas/dependency_graph.v1.json`

## Locked maps and CI

When a Carillion map is locked (`metrics.run_all --client carillion --lock`),
the run record written under `clients/carillion/maps/` records `method_tag`
(e.g. `carillion-method-v1`). Resolve the tag from `--method-tag` or from a
git tag on `HEAD` matching `{client}-method-v*`.

CI runs `python -m metrics.client_pack --check-method-freeze`. If
`clients/carillion/maps` contains a locked run record whose `method_tag`
points at a git tag whose `metrics/*.py` tree (including `thresholds.py`)
**differs** from the working tree, the check fails with a clear message.
Maps without `method_tag` are skipped (backward compatible). The backend
job checks out with `fetch-tags: true` and `fetch-depth: 0` so the
`method_tag` object is present (default shallow PR checkouts omit tags).

## Source pack and cut-off (not re-tagged by metric changes)

Evidence rules live with the client pack:

- Cut-off **2017-03-01** (inclusive)
- `clients/carillion/sources/manifest.yaml` — public sources only; URLs/metadata
- 2016 Annual Report (29 Mar 2017) excluded; primary financial sources are the
  1 Mar 2017 Final Results RNS and the 2015 Annual Report
- Known gaps (rating reports, agreed Dec 2016 pension valuation, facility /
  USPP / convertible instruments) → treat as fragile unknowns

See `clients/carillion/README.md`.

## Scoring (separate from this freeze)

Map lock and method tag stay immutable. Outcome comparison rules —
reference-list procedure, driver-level matching, reporting, integrity, and
contamination mitigations — live in
[ADR-020](../decisions/ADR-020-backtest-scoring.md). Findings feed a **new**
method tag (e.g. `carillion-method-v2`), never a retrofit of
`carillion-method-v1`.

## Out of scope of this freeze document

- Building the Carillion dependency model
- Performing the outcome comparison (see ADR-020; reference list and scoring
  are separate PRs)
- Creating the git tag (maintainer action on merge)
