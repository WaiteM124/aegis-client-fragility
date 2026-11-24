"""Slack: buffer and spare capacity relative to flow.

Formula
-------
For each edge e with flow f_e, capacity c_e, buffer b_e:

    spare_e  = max(c_e - f_e, 0)
    slack_e  = (spare_e + b_e) / f_e     if f_e > 0
             = +∞ (treated as well-buffered) if f_e == 0 and (c_e + b_e) > 0
             = 0                           if f_e == c_e == b_e == 0

Graph slack (bottleneck reading):

    Slack = min_e slack_e     over edges with f_e > 0
            (if no positive-flow edges, Slack = 0)

Meaning
-------
Slack measures structural headroom: spare capacity plus buffer stock
relative to current flow. Low slack means the graph is tightly loaded;
high slack means room to absorb a shock before flow is forced down.
This is an accounting identity on declared capacities — not a forecast
of demand spikes.

Status defaults
---------------
  green  if Slack ≥ 0.25
  amber  if Slack ≥ 0.10
  red    otherwise
"""

from __future__ import annotations

import argparse
import math

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock, edge_key
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "slack"
VERSION = "1.0.0"


def _edge_slack(flow: float, capacity: float, buffer: float) -> float:
    spare = max(capacity - flow, 0.0)
    if flow > 0:
        return (spare + buffer) / flow
    if capacity + buffer > 0:
        return math.inf
    return 0.0


def _status(value: float, thresholds: Thresholds) -> Status:
    t = thresholds.slack
    if value >= t.green_min:
        return Status.GREEN
    if value >= t.amber_min:
        return Status.AMBER
    return Status.RED


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    g = graph
    if scenario is not None:
        for ns in scenario.node_shocks:
            if ns.node_id in g:
                g = apply_node_shock(g, ns.node_id, ns.intensity)
        for es in scenario.edge_shocks:
            if g.has_edge(es.source, es.target):
                g = apply_edge_shock(g, es.source, es.target, es.intensity)

    per_edge: dict[str, float] = {}
    positive: dict[str, float] = {}
    for u, v, data in g.edges(data=True):
        flow = float(data.get("flow") or 0.0)
        capacity = float(data.get("capacity") or 0.0)
        buffer = float(data.get("buffer") or 0.0)
        s = _edge_slack(flow, capacity, buffer)
        key = edge_key(u, v)
        per_edge[key] = s if math.isfinite(s) else float("inf")
        if flow > 0:
            positive[key] = s

    if positive:
        bottleneck = min(positive.values())
        drivers = [e for e, s in sorted(positive.items(), key=lambda kv: kv[1]) if s == bottleneck]
        value = float(bottleneck)
    else:
        value = 0.0
        drivers = []

    finite_value = value if math.isfinite(value) else 1e9
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=finite_value if math.isfinite(value) else value,
        status=_status(finite_value, thresholds),
        drivers=drivers,
        inputs={
            "per_edge_slack": {k: (None if v == float("inf") else round(v, 6)) for k, v in per_edge.items()},
            "bottleneck": drivers[0] if drivers else None,
        },
        meaning=(
            f"Bottleneck slack={value if math.isfinite(value) else '∞'}. "
            "Low means little spare capacity/buffer relative to flow. "
            "Structural headroom — not a demand forecast."
        ),
        unit="ratio",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Compute structural slack (capacity/buffer vs flow).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
