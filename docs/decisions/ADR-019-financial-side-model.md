# ADR-019: Optional financial-side model (cash, covenants, contracts, customers, energy)

**Date:** 2026-11-25

## Context

Aegis graphs modelled the **supply** side well (suppliers, assets, routes, buyer
flow). Carillion’s public backtest (cut-off 2017-03-01) and ChillCo’s energy /
big-customer exposure need the **financial and sales** side too: cash and
liquidity, debt covenants as ruin lines, contracts, customer concentration, and
energy cost-to-margin. Extending the format must not break existing graphs,
examples, or evals, and must obey the non-negotiable principles: no prediction,
no blended score, deterministic maths, cited `worst_on_record` swings only,
unknowns flagged fragile.

## Decision

1. **Optional sections** on `DependencyGraphSpec` / graph YAML:
   `liquidity`, `covenants`, `contracts`, `customers`, `energy`. Omitting them
   leaves supply-only graphs valid. Related metrics return `NOT_TESTED` with
   `optional_section_absent=true` and are **excluded from group roll-up**, so
   existing group statuses stay identical.

2. **Covenants are ruin lines** alongside `survival_floor`. Each covenant has
   `kind` (max/min), `limit`, `current`, and a linked stress input whose cited
   `worst_on_record` is the swing size. Distance to breach = headroom / WOR.
   Ruin under an explicit probe reports **which line breaches first** (covenant
   id or survival floor). Missing `current` or missing cited WOR → fragile
   (red), never silently safe. The existing survival-floor path is unchanged.

3. **Customer vs supplier concentration stay separate.** `customer_hhi`,
   `customer_monoculture`, and `customer_spof` are labelled sales-side metrics.
   They are never merged with supplier HHI/monoculture/SPOF into one number
   ([ADR-008](ADR-008-no-blended-fragility-score.md)). `public_sector` is a
   customer attribute (Carillion-style government exposure).

4. **Contracts** carry pricing (`fixed` / `cost_plus`), margin, termination,
   loss exposure. Fixed-price + `input_cost_exposed` feeds the convexity harm
   curve (margin buffer then accelerating loss provisions).

5. **Energy** is an optional cost-share / pass-through block with a cited
   `worst_on_record`. Unrecovered share = cost_share × (1 − pass_through).

6. **Liquidity runway** = (cash + undrawn facilities) × (1 − δ) /
   fixed_monthly_outflows, with δ anchored on a cited WOR. Missing cash or
   outflows when the section is present → fragile.

7. **Schema.** `clients/schemas/dependency_graph.v1.json` documents the model
   (financial sections optional). Run-record metric rows stay the same shape —
   new metric names appear in the array; no DuckDB migration.

## Status

Accepted

## Consequences

- New modules: `runway`, `customer_hhi`, `customer_monoculture`, `customer_spof`,
  `energy_margin`; helpers in `metrics/finance.py`. `ruin` v3 and
  `distance_to_ruin` v2 incorporate covenants; `convexity` v2.1 includes
  fixed-price input-cost harm.
- `run_all` groups gain the new members; ChillCo EXAMPLE DATA exercises them.
- Eval cases: `covenant-001-breaches-before-floor`, `customer-001-dominant-spof`.
- No Carillion model numbers in this change (blind source pack remains separate).

## Alternatives rejected

- **Require financial sections on every graph.** Would break every existing
  example and eval; optional sections preserve identical supply-only results.
- **Blend customer and supplier HHI into one concentration score.** Hides which
  side is fragile; violates [ADR-008](ADR-008-no-blended-fragility-score.md).
- **Free sliders / AI-set swing sizes.** Forbidden — every swing is a cited
  `worst_on_record` with source and date ([ADR-006](ADR-006-no-prediction.md),
  [ADR-007](ADR-007-ai-never-scores.md)).
- **Replace survival_floor with covenants only.** Flow-floor remains a hard
  ruin line ([ADR-009](ADR-009-ruin-hard-red-flag.md)); covenants add lines,
  they do not remove the floor.
- **Silent defaults for missing cash / covenant current.** Unknowns must be
  flagged fragile — silence is not safety ([ADR-015](ADR-015-convexity-distance-to-ruin-not-tested.md)).
