"""Convexity / fragility heuristic (Taleb) via Jensen gap and a stress ladder.

Formula
-------
Let F₀ be deliverable inbound flow to the client on the intact graph.
For shock intensity δ ∈ {0.10, 0.20, 0.50}, apply the structural stress
response on every edge (see ``metrics.stress.edge_remaining``) and let
F(δ) be remaining deliverable flow. Loss:

    L(δ) = F₀ - F(δ)

Stress ladder: (L(0.10), L(0.20), L(0.50)).

Acceleration (normalised second difference):

    a₁ = (L(0.20) - L(0.10)) / 0.10
    a₂ = (L(0.50) - L(0.20)) / 0.30
    acceleration = a₂ - a₁

Jensen gap at the middle rung (vs linear interpolation from 0 to L(0.50)):

    jensen_gap = L(0.20) - (0.20 / 0.50) * L(0.50)

Classification of the payoff shape (payoff = remaining flow = F₀ − L):
  acceleration > 0  → losses accelerate → concave payoff → fragile
  acceleration ≈ 0  → linear → robust
  acceleration < 0  → losses decelerate → convex payoff → antifragile

Value reported = acceleration.

Meaning
-------
Taleb's structural fragility heuristic: whether harm accelerates as shock
size grows. Property of the graph's flow response under a stress ladder,
not a forecast of which shock will arrive.

Status defaults
---------------
  green  if acceleration ≤ 0 (robust or antifragile)
  amber  if fragile with small acceleration
  red    if acceleration > red_min (strongly accelerating loss)
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock
from metrics.stress import ensure_flow, stress_ladder_losses
from metrics.thresholds import STRESS_LADDER, THRESHOLDS, Thresholds

METRIC = "convexity"
VERSION = "1.0.0"


def _classify(acceleration: float, thresholds: Thresholds) -> tuple[Status, str]:
    t = thresholds.convexity
    if acceleration < -t.linear_tol:
        return Status.GREEN, "antifragile"
    if abs(acceleration) <= t.linear_tol:
        return Status.GREEN, "robust"
    if acceleration > t.red_min:
        return Status.RED, "fragile"
    return Status.AMBER, "fragile"


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    ladder: tuple[float, ...] = STRESS_LADDER,
) -> MetricResult:
    """Stress-ladder convexity reading (structural, not predictive)."""
    thresholds = thresholds or THRESHOLDS
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
    d10, d20, d50 = ladder[0], ladder[1], ladder[2]
    l10, l20, l50 = losses[d10], losses[d20], losses[d50]
    a1 = (l20 - l10) / (d20 - d10) if d20 != d10 else 0.0
    a2 = (l50 - l20) / (d50 - d20) if d50 != d20 else 0.0
    acceleration = a2 - a1
    linear_at_20 = (d20 / d50) * l50 if d50 else 0.0
    jensen_gap = l20 - linear_at_20

    status, shape = _classify(acceleration, thresholds)
    drivers = [
        f"loss@10%={l10:.4f}",
        f"loss@20%={l20:.4f}",
        f"loss@50%={l50:.4f}",
        f"shape={shape}",
    ]

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(acceleration),
        status=status,
        drivers=drivers,
        inputs={
            "F0": f0,
            "remaining": {str(k): v for k, v in remaining.items()},
            "losses": {str(k): v for k, v in losses.items()},
            "acceleration": acceleration,
            "jensen_gap_at_20": jensen_gap,
            "shape": shape,
            "ladder": list(ladder),
        },
        meaning=(
            f"Payoff shape={shape}; loss acceleration={acceleration:.6f}. "
            "Concave (accelerating loss) is fragile; linear is robust; "
            "convex is antifragile. Stress-ladder structural reading — "
            "not an event forecast."
        ),
        unit="acceleration",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Compute Taleb convexity / fragility heuristic (structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
