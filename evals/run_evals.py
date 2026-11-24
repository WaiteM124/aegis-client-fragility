#!/usr/bin/env python3
"""Deterministic eval suite for Aegis structural-fragility metrics.

Core principle: Aegis NEVER predicts. These evals test whether each metric
correctly FLAGS known structural weaknesses in labelled synthetic graphs.
They do not forecast events, estimate probabilities, or fit historical tails.

Reports
-------
  - per-metric detection recall (among cases that list the metric as a detector)
  - per-metric false-flag rate on robust controls (red on a control)
  - group-status accuracy (worst-member group status vs labelled expectation)
  - hard fail if any robust control is flagged red on any metric

Writes ``evals/results.json``. Exits non-zero when recall / group accuracy
drop below ``evals/baseline.json``, or when a control is flagged red.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from metrics.contracts import DependencyGraphSpec, MetricResult, Scenario, Status
from metrics.graph_loader import spec_to_networkx
from metrics.run_all import GROUPS, run_all, worst_status

EVALS_DIR = Path(__file__).resolve().parent
CASES_DIR = EVALS_DIR / "cases"
RESULTS_PATH = EVALS_DIR / "results.json"
BASELINE_PATH = EVALS_DIR / "baseline.json"

ALL_METRICS = [
    "hhi",
    "monoculture",
    "single_points_of_failure",
    "cascade_depth",
    "convexity",
    "ruin",
    "optionality",
    "slack",
]


def load_case(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: case must be a mapping")
    for key in ("id", "graph", "is_control"):
        if key not in raw:
            raise ValueError(f"{path}: missing required field {key!r}")
    raw.setdefault("detecting_metrics", [])
    raw.setdefault("expected_metric_status", {})
    raw.setdefault("expected_group_status", {})
    raw.setdefault("weakness", "unspecified")
    raw.setdefault("description", "")
    return raw


def load_cases(cases_dir: Path = CASES_DIR) -> list[dict[str, Any]]:
    paths = sorted(cases_dir.glob("*.yaml"))
    if not paths:
        raise FileNotFoundError(f"no case YAML files in {cases_dir}")
    return [load_case(p) for p in paths]


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    spec = DependencyGraphSpec.model_validate(case["graph"])
    graph = spec_to_networkx(spec)
    scenario = Scenario(name=case["id"])
    grouped = run_all(graph, scenario)

    metric_results: dict[str, MetricResult] = {}
    for _group, results in grouped.items():
        for r in results:
            metric_results[r.metric] = r

    group_status: dict[str, str] = {}
    for group_name, _ in GROUPS:
        force = group_name == "Convexity"
        status = worst_status(grouped[group_name], ruin_forces_red=force)
        group_status[group_name] = status.value

    return {
        "id": case["id"],
        "weakness": case["weakness"],
        "is_control": bool(case["is_control"]),
        "detecting_metrics": list(case["detecting_metrics"]),
        "metric_status": {m: r.status.value for m, r in metric_results.items()},
        "metric_value": {m: r.value for m, r in metric_results.items()},
        "group_status": group_status,
        "expected_group_status": dict(case.get("expected_group_status") or {}),
        "expected_metric_status": dict(case.get("expected_metric_status") or {}),
    }


def _is_flagged(status: str) -> bool:
    return status in ("amber", "red")


def summarise(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    # Per-metric recall
    detect_total: dict[str, int] = defaultdict(int)
    detect_hits: dict[str, int] = defaultdict(int)
    # False flags on controls (red only)
    control_total = 0
    control_red_by_metric: dict[str, int] = defaultdict(int)
    control_any_red = 0
    control_red_cases: list[dict[str, Any]] = []

    # Group accuracy
    group_checked = 0
    group_correct = 0
    group_mismatches: list[dict[str, Any]] = []

    # Explicit expected metric status checks (e.g. ruin just-above-floor → green)
    metric_expectation_checked = 0
    metric_expectation_correct = 0
    metric_expectation_mismatches: list[dict[str, Any]] = []

    recall_misses: list[dict[str, Any]] = []

    for cr in case_results:
        if cr["is_control"]:
            control_total += 1
            reds = {
                m: s for m, s in cr["metric_status"].items() if s == Status.RED.value
            }
            if reds:
                control_any_red += 1
                control_red_cases.append({"id": cr["id"], "red_metrics": reds})
            for m, s in cr["metric_status"].items():
                if s == Status.RED.value:
                    control_red_by_metric[m] += 1

        for m in cr["detecting_metrics"]:
            if m not in cr["metric_status"]:
                raise KeyError(f"case {cr['id']}: unknown detecting metric {m!r}")
            detect_total[m] += 1
            if _is_flagged(cr["metric_status"][m]):
                detect_hits[m] += 1
            else:
                recall_misses.append(
                    {
                        "id": cr["id"],
                        "metric": m,
                        "status": cr["metric_status"][m],
                    }
                )

        expected_groups = cr.get("expected_group_status") or {}
        for group_name, expected in expected_groups.items():
            group_checked += 1
            actual = cr["group_status"].get(group_name)
            if actual == expected:
                group_correct += 1
            else:
                group_mismatches.append(
                    {
                        "id": cr["id"],
                        "group": group_name,
                        "expected": expected,
                        "actual": actual,
                    }
                )

        for metric, expected in (cr.get("expected_metric_status") or {}).items():
            metric_expectation_checked += 1
            actual = cr["metric_status"].get(metric)
            if actual == expected:
                metric_expectation_correct += 1
            else:
                metric_expectation_mismatches.append(
                    {
                        "id": cr["id"],
                        "metric": metric,
                        "expected": expected,
                        "actual": actual,
                    }
                )

    recall: dict[str, float] = {}
    for m in ALL_METRICS:
        total = detect_total.get(m, 0)
        recall[m] = (detect_hits[m] / total) if total else 1.0

    false_flag_rate: dict[str, float] = {}
    for m in ALL_METRICS:
        false_flag_rate[m] = (
            (control_red_by_metric[m] / control_total) if control_total else 0.0
        )

    group_accuracy = (group_correct / group_checked) if group_checked else 1.0
    metric_expectation_accuracy = (
        (metric_expectation_correct / metric_expectation_checked)
        if metric_expectation_checked
        else 1.0
    )

    return {
        "n_cases": len(case_results),
        "n_controls": control_total,
        "n_weakness_cases": len(case_results) - control_total,
        "recall": recall,
        "detect_totals": dict(detect_total),
        "detect_hits": dict(detect_hits),
        "false_flag_rate": false_flag_rate,
        "control_red_by_metric": dict(control_red_by_metric),
        "controls_flagged_red": control_any_red,
        "control_red_cases": control_red_cases,
        "group_accuracy": group_accuracy,
        "group_checked": group_checked,
        "group_correct": group_correct,
        "group_mismatches": group_mismatches,
        "metric_expectation_accuracy": metric_expectation_accuracy,
        "metric_expectation_mismatches": metric_expectation_mismatches,
        "recall_misses": recall_misses,
    }


def fill_expected_group_status(
    cases: list[dict[str, Any]], case_results: list[dict[str, Any]]
) -> None:
    """Write actual group statuses back into case YAML when missing (bootstrap)."""
    by_id = {c["id"]: c for c in cases}
    for cr in case_results:
        case = by_id[cr["id"]]
        if case.get("expected_group_status"):
            continue
        case["expected_group_status"] = dict(cr["group_status"])
        path = CASES_DIR / f"{case['id']}.yaml"
        path.write_text(
            yaml.safe_dump(case, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        cr["expected_group_status"] = dict(cr["group_status"])


def compare_to_baseline(
    summary: dict[str, Any], baseline: dict[str, Any]
) -> list[str]:
    failures: list[str] = []

    if summary["controls_flagged_red"] > 0:
        failures.append(
            f"robust controls flagged red: {summary['controls_flagged_red']} "
            f"({summary['control_red_cases']})"
        )

    min_recall = baseline.get("min_recall", {})
    for metric, floor in min_recall.items():
        actual = summary["recall"].get(metric, 1.0)
        if actual + 1e-12 < float(floor):
            failures.append(
                f"recall[{metric}]={actual:.4f} below baseline {float(floor):.4f}"
            )

    min_group = float(baseline.get("min_group_accuracy", 1.0))
    if summary["group_accuracy"] + 1e-12 < min_group:
        failures.append(
            f"group_accuracy={summary['group_accuracy']:.4f} "
            f"below baseline {min_group:.4f}"
        )

    max_control_red = int(baseline.get("max_controls_flagged_red", 0))
    if summary["controls_flagged_red"] > max_control_red:
        failures.append(
            f"controls_flagged_red={summary['controls_flagged_red']} "
            f"exceeds baseline max {max_control_red}"
        )

    return failures


def build_results(
    case_results: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "principle": (
            "Evals measure structural weakness detection, not prediction. "
            "No event forecasting."
        ),
        "summary": {
            "n_cases": summary["n_cases"],
            "n_controls": summary["n_controls"],
            "n_weakness_cases": summary["n_weakness_cases"],
            "recall": summary["recall"],
            "false_flag_rate": summary["false_flag_rate"],
            "group_accuracy": summary["group_accuracy"],
            "controls_flagged_red": summary["controls_flagged_red"],
            "metric_expectation_accuracy": summary["metric_expectation_accuracy"],
        },
        "diagnostics": {
            "detect_totals": summary["detect_totals"],
            "detect_hits": summary["detect_hits"],
            "recall_misses": summary["recall_misses"],
            "group_mismatches": summary["group_mismatches"],
            "control_red_cases": summary["control_red_cases"],
            "metric_expectation_mismatches": summary["metric_expectation_mismatches"],
        },
        "cases": case_results,
    }


def default_baseline_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Snapshot current performance as the regression floor."""
    return {
        "description": (
            "Regression floor for structural weakness detection. "
            "Not a forecast quality target."
        ),
        "min_recall": {m: float(summary["recall"][m]) for m in ALL_METRICS},
        "min_group_accuracy": float(summary["group_accuracy"]),
        "max_controls_flagged_red": 0,
        "max_false_flag_rate": {
            m: float(summary["false_flag_rate"][m]) for m in ALL_METRICS
        },
    }


def print_report(summary: dict[str, Any]) -> None:
    print("Aegis metrics eval suite")
    print("Weakness detection only — no prediction.")
    print(
        f"cases={summary['n_cases']}  "
        f"weakness={summary['n_weakness_cases']}  "
        f"controls={summary['n_controls']}"
    )
    print()
    print("Per-metric detection recall")
    for m in ALL_METRICS:
        total = summary["detect_totals"].get(m, 0)
        hits = summary["detect_hits"].get(m, 0)
        print(f"  {m:28s}  recall={summary['recall'][m]:.3f}  ({hits}/{total})")
    print()
    print("False-flag rate on robust controls (red)")
    for m in ALL_METRICS:
        print(f"  {m:28s}  false_flag={summary['false_flag_rate'][m]:.3f}")
    print()
    print(
        f"group_status accuracy: {summary['group_accuracy']:.3f} "
        f"({summary['group_correct']}/{summary['group_checked']})"
    )
    print(f"controls flagged red:  {summary['controls_flagged_red']}")
    if summary["recall_misses"]:
        print("recall misses:")
        for miss in summary["recall_misses"]:
            print(f"  - {miss}")
    if summary["group_mismatches"]:
        print("group mismatches:")
        for miss in summary["group_mismatches"]:
            print(f"  - {miss}")
    if summary["control_red_cases"]:
        print("control red flags:")
        for item in summary["control_red_cases"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic structural-fragility metric evals "
            "(weakness detection, not prediction)."
        )
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=CASES_DIR,
        help="Directory of labelled case YAML files",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Path to write results JSON",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Baseline JSON regression floor",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Overwrite baseline.json from current results (bootstrap only)",
    )
    parser.add_argument(
        "--fill-expected-groups",
        action="store_true",
        help="Fill missing expected_group_status from actual metric output",
    )
    parser.add_argument(
        "--skip-baseline-check",
        action="store_true",
        help="Compute results without comparing to baseline",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases_dir)
    case_results = [evaluate_case(c) for c in cases]

    if args.fill_expected_groups:
        fill_expected_group_status(cases, case_results)
        # Re-attach expected groups after fill for accurate summary
        case_results = [evaluate_case(load_case(args.cases_dir / f"{c['id']}.yaml")) for c in cases]

    summary = summarise(case_results)
    print_report(summary)

    results = build_results(case_results, summary)
    args.results.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.results}")

    if args.write_baseline:
        baseline = default_baseline_from_summary(summary)
        args.baseline.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline {args.baseline}")

    if args.skip_baseline_check:
        # Still fail hard on control red flags — principle of the suite
        if summary["controls_flagged_red"] > 0:
            print("FAIL: robust control(s) flagged red", file=sys.stderr)
            return 1
        if summary["recall_misses"]:
            print("FAIL: detecting_metrics recall misses", file=sys.stderr)
            return 1
        if summary["metric_expectation_mismatches"]:
            print("FAIL: expected_metric_status mismatches", file=sys.stderr)
            return 1
        return 0

    if not args.baseline.exists():
        print(f"FAIL: baseline missing at {args.baseline}", file=sys.stderr)
        return 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    failures = compare_to_baseline(summary, baseline)

    # Always enforce labelled detecting_metrics and explicit metric expectations
    if summary["recall_misses"]:
        failures.append(f"recall misses: {summary['recall_misses']}")
    if summary["metric_expectation_mismatches"]:
        failures.append(
            f"metric expectation mismatches: {summary['metric_expectation_mismatches']}"
        )
    if summary["group_mismatches"]:
        failures.append(f"group mismatches: {summary['group_mismatches']}")

    if failures:
        print("\nEVAL GATE FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nEVAL GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
