---
name: add-metric
description: Step-by-step skill for adding a new Aegis structural-fragility metric. Use when introducing a new metric module under metrics/, wiring it into run_all / evals / run records, or writing its ADR. Enforces tests-first, one file per metric, own status (never a blended score), and docs.
---

# Add a fragility metric

Follow this skill whenever you add a new structural-fragility metric. Canonical principles live in `AGENTS.md` and product ADRs (especially ADR-006, ADR-007, ADR-008, ADR-009, ADR-010, ADR-014, ADR-015).

**Hard rules**

- Tests are the spec — write them **before** implementing `compute`.
- One module per metric with `compute(graph, scenario) -> MetricResult`.
- The metric keeps its **own** status (`red` / `amber` / `not_tested` / `green`). Never merge it into a blended or weighted single fragility score.
- Maths is deterministic Python only. No LLM calls, forecasts, probabilities, fitted tails, or historical-correlation estimates inside `compute`.
- Docs/config-only tasks must not change metric code; this skill is for metric work when that is the assigned task.

If the change also touches schemas, run-record shape, DuckDB migrations, or more than ~three files, obey `.cursor/rules/plan-first.mdc` (written plan, approved before coding).

---

## 0. Orient

1. Read `AGENTS.md` product principles and [ADR-010](../../../docs/decisions/ADR-010-one-file-per-metric.md).
2. Skim a neighbouring metric (e.g. `metrics/hhi.py` or `metrics/slack.py`) plus its tests and an eval case that lists it under `detecting_metrics`.
3. Confirm which **group** the metric belongs to (Concentration / Contagion / Convexity / Optionality) per [ADR-008](../../../docs/decisions/ADR-008-no-blended-fragility-score.md). Decided-but-missing members (e.g. hub dominance, hidden coupling, recovery time) still follow this skill — do not invent a blend to paper over the gap.
4. State the formula and plain-language meaning in one short paragraph before coding.

---

## 1. Write tests first (the spec)

### Unit tests (`metrics/tests/test_<metric>.py`)

- Known-answer / golden cases on small graphs (prefer YAML under `metrics/examples/` or inline fixtures matching `metrics/tests/conftest.py` patterns).
- Cover: happy path, edge cases, and red / amber / green (and `not_tested` when a required probe or input is missing).
- Assert **status and value**, not narrative copy alone.
- If the metric uses `worst_on_record`, missing anchors must yield `not_tested`, never a reassuring green ([ADR-015](../../../docs/decisions/ADR-015-convexity-distance-to-ruin-not-tested.md)).
- Do **not** assert on declared edge `stress_response` labels as the ground truth for convexity-shaped metrics — measure model output.

### Eval case(s) (`evals/cases/`)

Add **at least one** labelled case YAML that:

- Sets `detecting_metrics` to include the new metric id when it should flag a known weakness; and/or
- Updates a robust `is_control: true` case expectation if group status can change.

Case shape mirrors existing files (e.g. `evals/cases/mono-001-single-supplier.yaml`): `id`, `description`, `weakness`, `is_control`, `detecting_metrics`, `graph`, `expected_group_status`, optional `scenario` / `expected_metric_status`.

Also update `evals/run_evals.py` `ALL_METRICS` when the new id must appear in reports. Baseline bumps (`evals/baseline.json`) belong in an **intentional** commit after detection expectations change for justified reasons — not to hide a formula bug ([ADR-014](../../../docs/decisions/ADR-014-eval-gate-weakness-detection.md)). Fix formula bugs in a separate commit from harness/case changes.

Run until the new tests **fail for the right reason** (missing module / wrong status), then implement.

```bash
PYTHONPATH=. pytest metrics/tests/test_<metric>.py -q
PYTHONPATH=. python evals/run_evals.py   # after wiring; expect miss until compute exists
```

---

## 2. Implement the metric (`metrics/<name>.py`)

Required shape:

1. Module docstring with **Formula** and **Meaning** (plain language; no predictive framing).
2. `METRIC = "<snake_id>"` and `VERSION = "1.0.0"` (bump when semantics change).
3. `compute(graph: nx.DiGraph, scenario: Scenario | None = None, ...) -> MetricResult`.
4. Status via versioned thresholds in `metrics/thresholds.py` when cut-offs are numeric; keep thresholds structural, not probabilistic.
5. Optional CLI `main` via `metrics.cli_utils` so the metric runs standalone on YAML graphs ([ADR-010](../../../docs/decisions/ADR-010-one-file-per-metric.md)).

`MetricResult` must carry `metric`, `version`, `value`, `status`, `drivers`, `inputs`, `meaning`. Use `Status.NOT_TESTED` when the probe/data is absent — never treat untested as green.

**Forbidden inside `compute`**

- Event probabilities, fitted distributions, historical correlations, forecasts.
- LLM / model-gateway calls.
- Averaging or weighting this metric with others into a composite score.
- Free-slider or AI-chosen swing sizes — shock magnitudes for convexity / distance-to-ruin style probes come only from cited `worst_on_record` on graph inputs (with source and date in the client pack evidence), not invented numbers.

---

## 3. Register

| Where | What |
|---|---|
| `metrics/run_all.py` `GROUPS` | Add `(label, module.compute)` under the correct group. Group roll-up stays **worst** member (`red > amber > not_tested > green`). Ruin remains a hard red when tested. |
| `metrics/run_record.py` | No hard-coded metric list today — records whatever `run_all` returns. Still run record build/validate tests after registration. |
| `metrics/schemas/run_record.v1.json` / `v2.json` | Only if the record **shape** changes (new required fields, status enum, etc.). Prefer additive changes; plan first if migrating. |
| `metrics/store/migrations/` | Only if DuckDB columns/views must change ([ADR-017](../../../docs/decisions/ADR-017-local-duckdb-run-records.md)). |
| `evals/run_evals.py` `ALL_METRICS` | Append the metric id. |
| `metrics/thresholds.py` | Add a frozen thresholds dataclass + field on `Thresholds` when needed. |
| Example YAML | Add or extend `metrics/examples/` for CLI demos and unit fixtures. |

Do **not** add a cross-group aggregate, dashboard “overall fragility”, or weighted blend.

---

## 4. Document

1. **ADR** under `docs/decisions/ADR-NNN-<slug>.md` using the format in `docs/decisions/README.md` (Context / Decision / Status / Consequences / Alternatives rejected). Link related ADRs. Index it in `docs/decisions/README.md`.
2. Update `AGENTS.md` / README only if operator workflow or contracts change.
3. Module docstring is the in-code contract; keep formula and meaning accurate.

---

## 5. Verify before PR

```bash
make lint
PYTHONPATH=. pytest metrics/tests/ -q
PYTHONPATH=. python evals/run_evals.py
# or: make eval-gate
```

State assumptions in the PR (group membership, `not_tested` conditions, baseline impact). Keep the PR scoped to this metric.

---

## Checklist

Copy into the PR description and tick:

- [ ] Formula and plain-language meaning written (module docstring)
- [ ] Unit tests written **first** (known-answer + edge + status / `not_tested`)
- [ ] At least one eval case lists or exercises the metric; `ALL_METRICS` updated
- [ ] `metrics/<name>.py` with `compute(graph, scenario) -> MetricResult`
- [ ] Own status only — **no** blended / weighted single score
- [ ] Registered in `run_all.GROUPS` (correct group; worst-member roll-up unchanged)
- [ ] Thresholds / examples updated as needed
- [ ] Run record / schema / DuckDB touched only if required (plan-first if so)
- [ ] ADR written and indexed; no predictive copy
- [ ] `ruff` + `metrics/tests` + eval suite green
- [ ] Formula-bug fixes kept separate from harness/case/baseline commits
