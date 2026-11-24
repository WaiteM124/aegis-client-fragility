"""Optionality: number of node-disjoint supply paths (ways out).

Formula
-------
Let S be suppliers and c the client. A supply path is a directed simple
path from some s ∈ S to c. Two paths are considered disjoint when they
share no **asset** or **route** nodes (suppliers may feed more than one
path; the client is the shared sink).

    O = size of a maximum set of pairwise asset/route-disjoint supply paths

Computed by greedy packing of ``all_simple_paths`` over the (small)
dependency graphs this package targets: iterate suppliers, take each
simple path whose asset/route nodes are still free, mark those nodes used.

Value = O (integer as float).

Meaning
-------
O is how many independent structural corridors connect supply to the
client. O = 1 means a single corridor (brittle). O ≥ 2 means alternate
ways out. Counts topological optionality — not a forecast of path usage.

Status defaults
---------------
  green  if O ≥ 2
  amber  if O = 1
  red    if O = 0 (no path)
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock, client_id, supplier_ids
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "optionality"
VERSION = "1.0.0"


def _kind(graph: nx.DiGraph, node: str) -> str:
    return str(graph.nodes[node].get("kind") or "")


def _cut_nodes(graph: nx.DiGraph, path: list[str], client: str) -> set[str]:
    """Asset/route intermediates that make paths mutually exclusive."""
    return {
        n
        for n in path
        if n != client and _kind(graph, n) in {"asset", "route"}
    }


def count_optionality(graph: nx.DiGraph) -> tuple[int, list[list[str]]]:
    client = client_id(graph)
    suppliers = [s for s in supplier_ids(graph) if s in graph]
    if client not in graph or not suppliers:
        return 0, []

    paths: list[list[str]] = []
    used: set[str] = set()
    for s in suppliers:
        if s not in graph:
            continue
        try:
            candidates = list(nx.all_simple_paths(graph, s, client))
        except (nx.NetworkXError, nx.NodeNotFound):
            continue
        # Prefer shorter corridors first (stable, deterministic packing)
        candidates.sort(key=lambda p: (len(p), p))
        for path in candidates:
            cuts = _cut_nodes(graph, path, client)
            if cuts & used:
                continue
            paths.append(path)
            used |= cuts
    return len(paths), paths


def _status(value: int, thresholds: Thresholds) -> Status:
    t = thresholds.optionality
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

    o, paths = count_optionality(g)
    drivers = [f"path{i}:" + "→".join(p) for i, p in enumerate(paths, 1)]

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(o),
        status=_status(o, thresholds),
        drivers=drivers,
        inputs={"paths": paths, "client_id": client_id(graph), "suppliers": supplier_ids(graph)},
        meaning=(
            f"{o} node-disjoint supply path(s) to the client. "
            "More paths mean more structural ways out. "
            "Counts topology only — not path-usage forecasts."
        ),
        unit="paths",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Count node-disjoint supply paths (structural).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
