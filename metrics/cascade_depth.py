"""Cascade depth: how far a failure can propagate through the dependency graph.

Formula
-------
Working on the directed graph G (edges point supply → downstream):

If the scenario names shocked nodes/edges, seeds = those nodes (for an
edge shock, both endpoints). Otherwise seeds = all supplier nodes.

For each seed v, let d(v) be the length (edge count) of the longest
simple path from v to the client. Cascade depth:

    D = max_v d(v)

If the client is unreachable from a seed, that seed contributes 0.

Meaning
-------
D is the deepest structural contagion hop-count from the seed set to the
client. A long chain means a failure early in the graph can travel far
before reaching the buyer. This measures reach in the graph topology;
it does not estimate how likely a cascade is to start.

Status defaults
---------------
  green  if D ≤ 1
  amber  if D ≤ 3
  red    otherwise
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import client_id, supplier_ids
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "cascade_depth"
VERSION = "1.0.0"


def _longest_path_length(graph: nx.DiGraph, source: str, target: str) -> int:
    if source not in graph or target not in graph:
        return 0
    if source == target:
        return 0
    try:
        # Enumerate simple paths; graphs in this package are tiny.
        lengths = (len(p) - 1 for p in nx.all_simple_paths(graph, source, target))
        return max(lengths, default=0)
    except (nx.NetworkXError, nx.NodeNotFound):
        return 0


def _seeds(graph: nx.DiGraph, scenario: Scenario | None) -> list[str]:
    if scenario is None or (not scenario.node_shocks and not scenario.edge_shocks):
        return supplier_ids(graph)
    seeds: set[str] = set()
    for ns in scenario.node_shocks:
        seeds.add(ns.node_id)
    for es in scenario.edge_shocks:
        seeds.add(es.source)
        seeds.add(es.target)
    return sorted(seeds)


def _status(depth: int, thresholds: Thresholds) -> Status:
    t = thresholds.cascade_depth
    if depth <= t.green_max:
        return Status.GREEN
    if depth <= t.amber_max:
        return Status.AMBER
    return Status.RED


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    client = client_id(graph)
    seeds = _seeds(graph, scenario)
    per_seed = {s: _longest_path_length(graph, s, client) for s in seeds}
    depth = max(per_seed.values(), default=0)
    drivers = [s for s, d in sorted(per_seed.items(), key=lambda kv: -kv[1]) if d == depth and depth > 0]

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(depth),
        status=_status(depth, thresholds),
        drivers=drivers,
        inputs={"per_seed_depth": per_seed, "client_id": client, "seeds": seeds},
        meaning=(
            f"Cascade depth={depth} hops from seed set to client. "
            "High means failure can propagate far along the dependency chain. "
            "Topology reach only — not a cascade probability."
        ),
        unit="hops",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Compute cascade depth (structural).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
