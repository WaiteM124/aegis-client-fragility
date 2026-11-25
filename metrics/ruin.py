"""Ruin: whether an explicit stress probe crosses a point of no return.

Formula
-------
When an **explicit** probe is configured (scenario node/edge shocks,
``scenario.run_stress_ladder``, or an explicit ``ladder=`` argument),
using the stress ladder δ ∈ {0.10, 0.20, 0.50} by default (or scenario
override):

    F₀ = deliverable inbound flow to the client
    F(δ) = deliverable flow after structural stress at intensity δ

Survival floor resolution (first match wins):

    1. ``scenario.survival_floor`` (also set by CLI ``--survival-floor``)
    2. graph YAML / ``graph.graph["survival_floor"]`` (client-level override)
    3. ``thresholds.ruin.survival_floor`` (documented default **0.5**)

Ruin iff any δ in the ladder satisfies:

    F(δ) < floor × F₀     when F₀ > 0
    or F₀ ≤ 0             (no deliverable baseline)

Strict inequality: remaining exactly equal to the floor is not ruin.

When **no** explicit probe is configured, status is ``NOT_TESTED`` —
silence is not safety. An untested company must never look GREEN.

Value = 1.0 if ruin, else 0.0 (and 0.0 when not tested).

Meaning
-------
Ruin is a hard structural red flag: under an explicit stress probe,
deliverable flow falls below the client's survival floor. This is not a
probability of ruin — it flags that the graph's flow accounting admits a
below-floor state at a listed stress intensity.

Status
------
  not_tested  if no explicit shock / ladder probe is configured
  red         if ruin
  green       otherwise (explicitly tested and floor held)

``run_all`` forces the Convexity group to red whenever ruin is red.
``NOT_TESTED`` is never counted as a pass.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import (
    apply_edge_shock,
    apply_node_shock,
    client_id,
    deliverable_flow,
)
from metrics.stress import ensure_flow, stress_ladder_losses
from metrics.thresholds import STRESS_LADDER, THRESHOLDS, Thresholds

METRIC = "ruin"
VERSION = "2.0.0"


def resolve_survival_floor(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> float:
    """Resolve survival floor: scenario → graph YAML → thresholds default."""
    thresholds = thresholds or THRESHOLDS
    if scenario is not None and scenario.survival_floor is not None:
        return float(scenario.survival_floor)
    graph_floor = graph.graph.get("survival_floor")
    if graph_floor is not None:
        return float(graph_floor)
    ruin_line = graph.graph.get("ruin_line") or {}
    if isinstance(ruin_line, dict) and ruin_line.get("survival_floor") is not None:
        return float(ruin_line["survival_floor"])
    return float(thresholds.ruin.survival_floor)


def has_explicit_probe(
    scenario: Scenario | None,
    ladder: tuple[float, ...] | None = None,
) -> bool:
    """True when the caller opted into a ruin probe (shocks or ladder)."""
    if ladder is not None:
        return True
    if scenario is None:
        return False
    if scenario.run_stress_ladder:
        return True
    if scenario.node_shocks or scenario.edge_shocks:
        return True
    if scenario.stress_ladder:
        return True
    return False


def _resolve_ladder(
    scenario: Scenario,
    ladder: tuple[float, ...] | None,
) -> tuple[float, ...]:
    if ladder is not None:
        return ladder
    if scenario.stress_ladder:
        return tuple(float(x) for x in scenario.stress_ladder)
    return STRESS_LADDER


def _apply_shocks(graph: nx.DiGraph, scenario: Scenario) -> nx.DiGraph:
    g = graph
    for ns in scenario.node_shocks:
        if ns.node_id in g:
            g = apply_node_shock(g, ns.node_id, ns.intensity)
    for es in scenario.edge_shocks:
        if g.has_edge(es.source, es.target):
            g = apply_edge_shock(g, es.source, es.target, es.intensity)
    return g


def _result(
    *,
    is_ruin: bool,
    crossed: list[str],
    f0: float,
    remaining: dict,
    losses: dict,
    floor: float,
    probe: str,
) -> MetricResult:
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=1.0 if is_ruin else 0.0,
        status=Status.RED if is_ruin else Status.GREEN,
        drivers=crossed if is_ruin else [],
        inputs={
            "F0": f0,
            "remaining": {str(k): v for k, v in remaining.items()},
            "losses": {str(k): v for k, v in losses.items()},
            "survival_floor": floor,
            "threshold_flow": floor * f0 if f0 > 0 else 0.0,
            "crossed_rungs": crossed,
            "probe": probe,
        },
        meaning=(
            ("RUIN: an explicit stress probe fell below the survival floor. ")
            if is_ruin
            else "Explicit probe: no rung fell below the survival floor. "
        )
        + f"Floor={floor:.2f} of baseline. Hard structural flag — not a probability of ruin.",
        unit="flag",
    )


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    ladder: tuple[float, ...] | None = None,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    scenario = scenario or Scenario()

    if not has_explicit_probe(scenario, ladder):
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={
                "reason": "no_explicit_shock",
                "hint": (
                    "Set scenario.run_stress_ladder, pass ladder=, "
                    "or configure node/edge shocks."
                ),
            },
            meaning=(
                "NOT TESTED: no explicit shock or stress-ladder probe configured. "
                "Silence is not safety — ruin is untested, not green."
            ),
            unit="flag",
        )

    floor = resolve_survival_floor(graph, scenario, thresholds)
    use_ladder = _resolve_ladder(scenario, ladder)
    wants_ladder = (
        scenario.run_stress_ladder
        or scenario.stress_ladder is not None
        or ladder is not None
    )
    has_shocks = bool(scenario.node_shocks or scenario.edge_shocks)

    g = ensure_flow(_apply_shocks(graph, scenario))
    sink = client_id(graph)
    f0_intact = deliverable_flow(ensure_flow(graph), sink)

    if has_shocks and not wants_ladder:
        f_shocked = deliverable_flow(g, sink if sink in g else None)
        remaining = {"shocked": f_shocked}
        losses = {"shocked": max(f0_intact - f_shocked, 0.0)}
        crossed: list[str] = []
        if f0_intact <= 0 or f_shocked < floor * f0_intact:
            crossed = ["shocked"]
        return _result(
            is_ruin=len(crossed) > 0,
            crossed=crossed,
            f0=f0_intact,
            remaining=remaining,
            losses=losses,
            floor=floor,
            probe="shock",
        )

    # Ladder probe (optionally after shocks)
    f0, remaining, losses = stress_ladder_losses(g, use_ladder)
    crossed = []
    if f0 <= 0:
        crossed = [f"delta={d}" for d in use_ladder]
    else:
        threshold_flow = floor * f0
        for delta, f in remaining.items():
            if f < threshold_flow:
                crossed.append(f"delta={delta}")

    return _result(
        is_ruin=len(crossed) > 0,
        crossed=crossed,
        f0=f0,
        remaining=remaining,
        losses=losses,
        floor=floor,
        probe="shock+ladder" if has_shocks else "ladder",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Detect structural ruin on an explicit stress probe."
    )
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help=(
            "Ruin when remaining flow < FRAC × baseline F0 at any ladder rung. "
            "Overrides graph YAML and the default (0.5 in metrics.thresholds)."
        ),
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    # --stress-ladder is on common args and already folded into scenario
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
