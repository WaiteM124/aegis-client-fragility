"""Energy cost unrecovered into margin (structural input-cost exposure).

Formula
-------
When the optional ``energy`` section is present:

    unrecovered = cost_share × (1 − pass_through_pct)
    margin_hit_at_wor = unrecovered × worst_on_record

``worst_on_record`` is a cited energy-price move (fraction) with source
and date — never an AI-set slider. No probability is attached.

Status (versioned ``EnergyMarginThresholds``)
--------------------------------------------
  red    if unrecovered > red_min (default 0.15)
  amber  if unrecovered > amber_min (default 0.05)
  green  otherwise when fully specified
  RED    if section present but required fields missing (fragile unknown)
  not_tested if section absent (``optional_section_absent``)

Meaning
-------
How much of the cost base is energy that cannot be passed through, linked
to margin. Structural exposure reading — not a forecast of energy prices.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.finance import (
    graph_energy,
    has_energy,
    section_absent_result,
    unrecovered_energy_share,
)
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "energy_margin"
VERSION = "1.0.0"


def _status(unrecovered: float, thresholds: Thresholds) -> Status:
    t = thresholds.energy_margin
    if unrecovered > t.red_min:
        return Status.RED
    if unrecovered > t.amber_min:
        return Status.AMBER
    return Status.GREEN


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    _ = scenario
    thresholds = thresholds or THRESHOLDS

    if not has_energy(graph):
        return section_absent_result(
            metric=METRIC, version=VERSION, section="energy", unit="share"
        )

    energy = graph_energy(graph)
    assert energy is not None
    unrecovered, unknown = unrecovered_energy_share(energy)
    if energy.worst_on_record is None:
        unknown = list(unknown) + ["worst_on_record"]

    if unknown or unrecovered is None:
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
                "FRAGILE: energy section present but required fields missing "
                f"({', '.join(unknown)}). Unknowns are flagged fragile — never "
                "silently treated as safe. Not an energy-price forecast."
            ),
            unit="share",
        )

    wor = float(energy.worst_on_record)  # type: ignore[arg-type]
    margin_hit = float(unrecovered) * wor
    status = _status(float(unrecovered), thresholds)

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(unrecovered),
        status=status,
        drivers=[
            f"unrecovered={unrecovered:.4f}",
            f"margin_hit_at_wor={margin_hit:.4f}",
        ],
        inputs={
            "cost_share": energy.cost_share,
            "pass_through_pct": energy.pass_through_pct,
            "unrecovered_share": unrecovered,
            "worst_on_record": wor,
            "margin_hit_at_wor": margin_hit,
            "source": energy.source.model_dump() if energy.source else None,
            "threshold_version": thresholds.energy_margin.version,
        },
        meaning=(
            f"Unrecovered energy share={unrecovered:.4f}; "
            f"margin hit at cited worst_on_record={margin_hit:.4f}. "
            "Structural input-cost exposure — not an energy-price forecast."
        ),
        unit="share",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Energy cost unrecovered into margin (structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
