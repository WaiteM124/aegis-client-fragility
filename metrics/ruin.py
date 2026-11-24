"""Ruin: whether any rung of the stress ladder crosses a point of no return.

Formula
-------
Using the same stress ladder as convexity (δ ∈ {0.10, 0.20, 0.50}):

    F₀ = deliverable inbound flow to the client
    F(δ) = deliverable flow after structural stress at intensity δ
    floor = scenario.survival_floor if set, else thresholds.ruin.survival_floor
            (default 0.0)

Ruin iff any δ in the ladder satisfies:

    F(δ) ≤ floor * F₀     when F₀ > 0 and floor > 0
    F(δ) ≤ 0              when floor == 0
    or F₀ ≤ 0             (no deliverable baseline)

Value = 1.0 if ruin, else 0.0.

Meaning
-------
Ruin is a hard structural red flag: under the stress ladder, deliverable
flow crosses the survival floor (point of no return). Not a probability
of ruin — it flags that the graph's flow accounting admits a
zero/below-floor state at a listed stress intensity.

Status
------
  red    if ruin
  green  otherwise

``run_all`` forces the Convexity group to red whenever ruin is red.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock
from metrics.stress import ensure_flow, stress_ladder_losses
from metrics.thresholds import STRESS_LADDER, THRESHOLDS, Thresholds

METRIC = "ruin"
VERSION = "1.0.0"


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    ladder: tuple[float, ...] = STRESS_LADDER,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    floor = thresholds.ruin.survival_floor
    if scenario is not None and scenario.survival_floor is not None:
        floor = scenario.survival_floor

    g = graph
    if scenario is not None:
        for ns in scenario.node_shocks:
            if ns.node_id in g:
                g = apply_node_shock(g, ns.node_id, ns.intensity)
        for es in scenario.edge_shocks:
            if g.has_edge(es.source, es.target):
                g = apply_edge_shock(g, es.source, es.target, es.intensity)

    g = ensure_flow(g)
    f0, remaining, losses = stress_ladder_losses(g, ladder)

    crossed: list[str] = []
    if f0 <= 0:
        crossed = [f"delta={d}" for d in ladder]
    else:
        for delta, f in remaining.items():
            if floor <= 0.0:
                if f <= 0.0:
                    crossed.append(f"delta={delta}")
            elif f <= floor * f0 + 1e-15:
                crossed.append(f"delta={delta}")

    is_ruin = len(crossed) > 0
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
            "crossed_rungs": crossed,
        },
        meaning=(
            ("RUIN: a stress-ladder rung crossed the survival floor. ")
            if is_ruin
            else "No ladder rung crossed the survival floor. "
        )
        + "Hard structural flag — not a probability of ruin.",
        unit="flag",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Detect structural ruin on the stress ladder.")
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        help="Fraction of baseline flow at/below which is ruin (default from thresholds).",
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
