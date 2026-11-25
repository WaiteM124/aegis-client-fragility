---
name: add-metric
description: Step-by-step skill for adding a new Aegis structural-fragility metric. Use when introducing a new metric module under metrics/, wiring it into run_all / evals / run records, or writing its ADR. Enforces tests-first, one file per metric, own status (never a blended score), and docs. Covers supply-side and optional financial-side metrics (ADR-019).
---

# Add a fragility metric

Follow this skill whenever you add a new structural-fragility metric. Canonical principles live in `AGENTS.md` and product ADRs (especially ADR-006, ADR-007, ADR-008, ADR-009, ADR-010, ADR-014, ADR-015, [ADR-019](../../../docs/decisions/ADR-019-financial-side-model.md)).

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
2. Skim a neighbouring metric plus its tests and an eval case that lists it under `detecting_metrics`:
   - Supply-side: e.g. `metrics/hhi.py`, `metrics/slack.py`.
   - Financial-side (ADR-019): e.g. `metrics/runway.py`, `metrics/customer_hhi.py`, `metrics/energy_margin.py`; shared helpers in `metrics/finance.py`. Covenant ruin lines live in `metrics/ruin.py` / `metrics/distance_to_ruin.py` (not separate blendable scores).
3. Confirm which **group** the metric belongs to (Concentration / Contagion / Convexity / Optionality) per [ADR-008](../../../docs/decisions/ADR-008-no-blended-fragility-score.md). Current financial members (do not invent a blend):
   - **Concentration** — also `customer_hhi`, `customer_monoculture` (sales-side; never merged with supplier HHI/monoculture).
   - **Contagion** — also `customer_spof`.
   - **Convexity** — also `runway`, `energy_margin`; covenants extend `ruin` / `distance_to_ruin` as additional ruin lines beside `survival_floor`.
4. If the metric depends on optional graph sections (`liquidity`, `covenants`, `contracts`, `customers`, `energy` in `DependencyGraphSpec` / `clients/schemas/dependency_graph.v1.json`), plan the absent-section behaviour (see below).
5. State the formula and plain-language meaning in one short paragraph before coding.

---

## 1. Write tests first (the spec)

### Unit tests (`metrics/tests/test_<metric>.py`)

- Known-answer / golden cases on small graphs (prefer YAML under `metrics/examples/` or inline fixtures matching `metrics/tests/conftest.py` / `metrics/tests/test_finance_model.py` patterns).
- Cover: happy path, edge cases, and red / amber / green (and `not_tested` when a required probe or input is missing).
- Assert **status and value**, not narrative copy alone.
- If the metric uses `worst_on_record`, missing anchors must not look safe: prefer `not_tested` for absent probes ([ADR-015](../../../docs/decisions/ADR-015-convexity-distance-to-ruin-not-tested.md)); when an optional financial section is **present** but required fields (e.g. cash, covenant `current`, cited WOR) are missing → **fragile (red)**, never silently green ([ADR-019](../../../docs/decisions/ADR-019-financial-side-model.md)).
- Do **not** assert on declared edge `stress_response` labels as the ground truth for convexity-shaped metrics — measure model output.
- For optional-section metrics: assert that omitting the section returns `NOT_TESTED` with `inputs["optional_section_absent"]=true` (excluded from group roll-up in `run_all`).

### Eval case(s) (`evals/cases/`)

Add **at least one** labelled case YAML that:

- Sets `detecting_metrics` to include the new metric id when it should flag a known weakness; and/or
- Updates a robust `is_control: true` case expectation if group status can change.

Case shape mirrors existing files (e.g. `evals/cases/mono-001-single-supplier.yaml`, `evals/cases/covenant-001-breaches-before-floor.yaml`, `evals/cases/customer-001-dominant-spof.yaml`): `id`, `description`, `weakness`, `is_control`, `detecting_metrics`, `graph`, `expected_group_status`, optional `scenario` / `expected_metric_status`.

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

**Optional financial sections (ADR-019)**

- Graph YAML / `DependencyGraphSpec` may include `liquidity`, `covenants`, `contracts`, `customers`, `energy` (schema: `clients/schemas/dependency_graph.v1.json`). Omitting them keeps supply-only graphs valid.
- If your metric needs a section that is absent → `NOT_TESTED` + `optional_section_absent=true`. `run_all.worst_status` **excludes** those results from group roll-up so existing group statuses stay identical.
- Customer metrics stay labelled sales-side; never average or merge them with supplier HHI / monoculture / SPOF.
- Covenants are **additional ruin lines** beside `survival_floor` (extend `ruin` / `distance_to_ruin`, report which line breaches first). Do not replace the floor or invent a separate blended “financial ruin score”.
- Prefer shared parsing/helpers in `metrics/finance.py` over duplicating covenant/liquidity math.

**Forbidden inside `compute`**

- Event probabilities, fitted distributions, historical correlations, forecasts.
- LLM / model-gateway calls.
- Averaging or weighting this metric with others into a composite score (including supplier+customer blends).
- Free-slider or AI-chosen swing sizes — shock magnitudes (convexity, distance-to-ruin, runway δ, covenant headroom, energy unrecovered share, etc.) come only from cited `worst_on_record` on graph inputs / section fields (with `source` + date in pack evidence), not invented numbers.

---

## 3. Register

| Where | What |
|---|---|
| `metrics/run_all.py` `GROUPS` | Add `(label, module.compute)` under the correct group. Group roll-up stays **worst** member (`red > amber > not_tested > green`), excluding `optional_section_absent` NOT_TESTED. Ruin remains a hard red when tested. |
| `metrics/run_record.py` | No hard-coded metric list today — records whatever `run_all` returns (new names appear in the metrics array). Still run record build/validate tests after registration. New metric **names** alone do not require a DuckDB migration ([ADR-019](../../../docs/decisions/ADR-019-financial-side-model.md)). |
| `metrics/schemas/run_record.v1.json` / `v2.json` | Only if the record **shape** changes (new required fields, status enum, etc.). Prefer additive changes; plan first if migrating. |
| `clients/schemas/dependency_graph.v1.json` + `metrics/contracts.py` | When adding optional financial (or other) graph fields the metric needs. |
| `metrics/store/migrations/` | Only if DuckDB columns/views must change ([ADR-017](../../../docs/decisions/ADR-017-local-duckdb-run-records.md)). |
| `evals/run_evals.py` `ALL_METRICS` | Append the metric id. |
| `metrics/thresholds.py` | Add a frozen thresholds dataclass + field on `Thresholds` when needed. |
| Example YAML | Add or extend `metrics/examples/` and/or client pack models (e.g. ChillCo) for CLI demos and unit fixtures. |

Do **not** add a cross-group aggregate, dashboard “overall fragility”, or weighted blend.

---

## 4. Document

1. **ADR** under `docs/decisions/ADR-NNN-<slug>.md` using the format in `docs/decisions/README.md` (Context / Decision / Status / Consequences / Alternatives rejected). Link related ADRs (include ADR-019 when financial-side). Index it in `docs/decisions/README.md`.
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

State assumptions in the PR (group membership, `not_tested` / `optional_section_absent` conditions, baseline impact). Keep the PR scoped to this metric.

---

## Checklist

Copy into the PR description and tick:

- [ ] Formula and plain-language meaning written (module docstring)
- [ ] Unit tests written **first** (known-answer + edge + status / `not_tested` / fragile-unknowns)
- [ ] At least one eval case lists or exercises the metric; `ALL_METRICS` updated
- [ ] `metrics/<name>.py` with `compute(graph, scenario) -> MetricResult`
- [ ] Own status only — **no** blended / weighted single score (no supplier↔customer merge)
- [ ] Registered in `run_all.GROUPS` (correct group; worst-member roll-up; optional-section exclusion if applicable)
- [ ] If financial-side: optional sections + cited `worst_on_record`; covenants as ruin lines when relevant; schema/contracts updated
- [ ] Thresholds / examples updated as needed
- [ ] Run record / schema / DuckDB touched only if required (plan-first if so)
- [ ] ADR written and indexed; no predictive copy
- [ ] `ruff` + `metrics/tests` + eval suite green
- [ ] Formula-bug fixes kept separate from harness/case/baseline commits
