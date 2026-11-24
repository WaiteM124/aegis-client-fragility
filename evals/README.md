# Metrics eval suite

**Weakness detection, not prediction.** These evals check that deterministic
structural-fragility metrics correctly **flag** known weaknesses in labelled
synthetic dependency graphs. They do not forecast events. See
[ADR-014](../docs/decisions/ADR-014-eval-gate-weakness-detection.md).

## Layout

| Path | Role |
|---|---|
| `cases/*.yaml` | Labelled graphs: weakness tag, `detecting_metrics`, `expected_group_status`, optional `expected_metric_status`, plus the graph |
| `run_evals.py` | Runner — recall, false-flag rate on controls, group accuracy → `results.json` |
| `baseline.json` | Regression floor committed to git |
| `results.json` | Last local / CI run output |
| `_generate_cases.py` | Maintainer helper to regenerate case YAML (not used by CI) |

## Run

```bash
PYTHONPATH=. python evals/run_evals.py
# or
make eval-gate
```

CI job `eval-gate` runs the suite on every PR and also `pytest -m evaluation`
(offline; no API keys).

## Case coverage

- Single-supplier / attribute monoculture
- Hidden single point of failure behind apparent redundancy
- Deep cascade chains
- Concave (fragile) loss under the 10/20/50% stress ladder
- Ruin below the 0.5 survival floor and just at/above it
- Low optionality and slack
- Well-diversified robust controls (must not be flagged **red**)
