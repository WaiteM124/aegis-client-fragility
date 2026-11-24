# ADR-010: One file per metric

**Date:** 2026-11-23

## Context

Fragility maths must stay inspectable and independently testable. Bundling many metrics into one service or UI-first module makes formulas hard to review and couples scoring to presentation or AI.

## Decision

Each fragility metric lives in **one module** with:

- a `compute(graph, scenario) -> MetricResult` function;
- a module docstring that states the **formula** and its **plain-language meaning**.

Each metric must run **standalone from the CLI** on YAML example graphs and be tested on toy graphs **before** any UI or AI integration.

## Status

Accepted

## Consequences

- Package layout is top-level `metrics/` (not under `backend/`): one file per metric (`hhi.py`, `monoculture.py`, `ruin.py`, …), shared helpers (`stress.py`, `thresholds.py`, `contracts.py`, `graph_loader.py`), YAML examples in `metrics/examples/`, tests in `metrics/tests/`.
- CLI entry points live on each metric module and on `metrics/run_all.py` via `cli_utils`.
- New metrics follow the same pattern; do not gate them on dashboard or model-provider work.

## Alternatives rejected

- **Monolithic scoring service** — harder to inspect and golden-test per formula.
- **UI- or AI-first metrics** — couples maths to presentation and blurs the deterministic boundary ([ADR-007](ADR-007-ai-never-scores.md)).
