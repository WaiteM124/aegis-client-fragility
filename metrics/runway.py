"""Liquidity runway in months under structural cash stress.

Formula
-------
When the optional ``liquidity`` section is present:

    available = cash_on_hand + Σ undrawn committed facilities
    runway_months = available / fixed_monthly_outflows

Under an explicit stress intensity δ (from a cited worst_on_record
multiple on the linked liquidity stress input, or a ladder probe):

    runway_stressed(δ) = available × (1 − δ) / fixed_monthly_outflows

δ is a structural scan intensity anchored on worst_on_record — not a
probability of cash loss.

When ``liquidity`` is absent → NOT_TESTED with ``optional_section_absent``.
When present but cash / outflows missing → RED (fragile; never silent safe).

Status (versioned ``RunwayThresholds``)
--------------------------------------
  red    if runway < red_max_months (default 3)
  amber  if runway < amber_max_months (default 6)
  green  otherwise
  not_tested / red as above for missing data

Meaning
-------
How many months of fixed outflows the declared cash + undrawn facilities
cover. Structural liquidity headroom — not a forecast of when cash runs out.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.finance import (
    available_liquidity,
    graph_liquidity,
    has_liquidity,
    input_worst_on_record,
    section_absent_result,
)
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "runway"
VERSION = "1.0.0"


def _status(months: float, thresholds: Thresholds) -> Status:
    t = thresholds.runway
    if months < t.red_max_months:
        return Status.RED
    if months < t.amber_max_months:
        return Status.AMBER
    return Status.GREEN


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    *,
    stress_intensity: float | None = None,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    scenario = scenario or Scenario()
    _ = scenario

    if not has_liquidity(graph):
        return section_absent_result(
            metric=METRIC, version=VERSION, section="liquidity", unit="months"
        )

    liq = graph_liquidity(graph)
    assert liq is not None

    unknown: list[str] = []
    if liq.fixed_monthly_outflows is None:
        unknown.append("fixed_monthly_outflows")
    avail, cash_unknown = available_liquidity(liq)
    unknown.extend(cash_unknown)

    if unknown:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.RED,
            drivers=[f"unknown:{u}" for u in unknown],
            inputs={
                "reason": "missing_required_fields",
                "unknown_fields": unknown,
                "fragile_unknown": True,
            },
            meaning=(
                "FRAGILE: liquidity section present but required fields missing "
                f"({', '.join(unknown)}). Unknowns are flagged fragile — never "
                "silently treated as safe. Not a cash-flow forecast."
            ),
            unit="months",
        )

    assert avail is not None
    assert liq.fixed_monthly_outflows is not None
    outflows = float(liq.fixed_monthly_outflows)
    if outflows <= 0:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.RED,
            drivers=["fixed_monthly_outflows<=0"],
            inputs={"available": avail, "fixed_monthly_outflows": outflows},
            meaning=(
                "FRAGILE: fixed_monthly_outflows is zero or negative — runway "
                "undefined. Structural flag, not a forecast."
            ),
            unit="months",
        )

    delta = 0.0
    stress_source = "none"
    if stress_intensity is not None:
        delta = max(0.0, min(1.0, float(stress_intensity)))
        stress_source = "explicit"
    else:
        wor, _inp = input_worst_on_record(graph, liq.stress_input_id)
        if wor is not None and wor > 0:
            # One × worst_on_record as the structural stress reading.
            delta = max(0.0, min(1.0, float(wor)))
            stress_source = f"worst_on_record:{liq.stress_input_id}"

    stressed_avail = avail * (1.0 - delta)
    months = stressed_avail / outflows
    status = _status(months, thresholds)
    undrawn = sum(float(f.undrawn) for f in liq.committed_facilities)

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(months),
        status=status,
        drivers=[
            f"runway_months={months:.3f}",
            f"stress_delta={delta:.4f}",
        ],
        inputs={
            "cash_on_hand": liq.cash_on_hand,
            "undrawn_facilities": undrawn,
            "available": avail,
            "available_stressed": stressed_avail,
            "fixed_monthly_outflows": outflows,
            "stress_delta": delta,
            "stress_source": stress_source,
            "threshold_version": thresholds.runway.version,
            "red_max_months": thresholds.runway.red_max_months,
            "amber_max_months": thresholds.runway.amber_max_months,
        },
        meaning=(
            f"Liquidity runway={months:.2f} months under stress δ={delta:.3f}. "
            "available=(cash+undrawn)×(1−δ) / fixed monthly outflows. "
            "Structural headroom — not a forecast of insolvency timing."
        ),
        unit="months",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Liquidity runway in months (structural; no forecast)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
