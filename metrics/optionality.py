"""Optionality: number of node-disjoint supply paths (ways out).

Formula
-------
Let S be suppliers and c the client (buyer). Introduce a super-source σ
with an edge σ → s for every s ∈ S. A supply corridor is a directed path
from σ to c. Two corridors are **node-disjoint** when they share no
vertices other than σ and c — including supplier nodes. A shared source
therefore collapses corridors that only look independent downstream.

    O = max number of pairwise node-disjoint σ→c paths
      = max-flow in the node-split residual network (Menger)

Node splitting: every vertex v ∉ {σ, c} becomes v_in → v_out with
capacity 1; each original edge u → v becomes u_out → v_in with capacity
∞ (σ and c are not split). Max-flow σ → c equals O.

Value = O (integer as float).

Meaning
-------
O is how many independent structural corridors connect supply to the
client. O = 1 means a single corridor (brittle) — even when multiple
apparent routes share an upstream node. O ≥ 2 means alternate ways out
that do not share any internal node. Counts topological optionality —
not a forecast of path usage.

Drivers
-------
Packed path listings plus ``shared_collapse:<node>`` for every node that
lies on all supplier→client simple paths when O is constrained by a
shared vertex (the node that collapses the apparent routes).

Status defaults
---------------
  green  if O ≥ 2
  amber  if O = 1
  red    if O = 0 (no path)
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock, client_id, supplier_ids
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "optionality"
VERSION = "2.0.0"

_SUPER = "__optionality_super__"
_INF = 10**9


def _split_id(node: str, side: str) -> str:
    return f"{node}::{side}"


def _build_node_split_flow_graph(
    graph: nx.DiGraph, suppliers: list[str], client: str
) -> nx.DiGraph:
    """Unit-capacity node-split network for Menger node-disjoint paths."""
    flow = nx.DiGraph()
    # Split every original node except the sink (client).
    for n in graph.nodes:
        if n == client:
            continue
        flow.add_edge(_split_id(n, "in"), _split_id(n, "out"), capacity=1.0)

    for u, v in graph.edges:
        u_out = _SUPER if u == _SUPER else (
            client if u == client else _split_id(u, "out")
        )
        v_in = client if v == client else _split_id(v, "in")
        # Should not happen for a normal supply DAG, but keep deterministic.
        if u == client:
            continue
        flow.add_edge(u_out, v_in, capacity=float(_INF))

    # Super-source feeds every supplier (suppliers are split, so shared
    # source capacity is 1 and collapses co-starting corridors).
    for s in suppliers:
        if s not in graph:
            continue
        flow.add_edge(_SUPER, _split_id(s, "in"), capacity=float(_INF))
    return flow


def _max_node_disjoint(graph: nx.DiGraph, suppliers: list[str], client: str) -> int:
    if client not in graph or not suppliers:
        return 0
    flow_g = _build_node_split_flow_graph(graph, suppliers, client)
    if _SUPER not in flow_g or client not in flow_g:
        return 0
    try:
        flow_value = nx.maximum_flow_value(flow_g, _SUPER, client)
    except nx.NetworkXError:
        return 0
    return int(flow_value)


def _pack_paths(graph: nx.DiGraph, suppliers: list[str], client: str, limit: int) -> list[list[str]]:
    """Greedy pack of node-disjoint simple paths (suppliers included as cuts)."""
    if limit <= 0:
        return []
    paths: list[list[str]] = []
    used: set[str] = set()
    candidates: list[list[str]] = []
    for s in suppliers:
        if s not in graph:
            continue
        try:
            found = list(nx.all_simple_paths(graph, s, client))
        except (nx.NetworkXError, nx.NodeNotFound):
            continue
        candidates.extend(found)
    candidates.sort(key=lambda p: (len(p), p))
    for path in candidates:
        if len(paths) >= limit:
            break
        internal = [n for n in path if n != client]
        if used.intersection(internal):
            continue
        paths.append(path)
        used.update(internal)
    return paths


def _nodes_on_all_paths(graph: nx.DiGraph, suppliers: list[str], client: str) -> list[str]:
    """Nodes (excluding client) that lie on every supplier→client simple path."""
    all_paths: list[list[str]] = []
    for s in suppliers:
        if s not in graph:
            continue
        try:
            all_paths.extend(nx.all_simple_paths(graph, s, client))
        except (nx.NetworkXError, nx.NodeNotFound):
            continue
    if not all_paths:
        return []
    common: set[str] | None = None
    for path in all_paths:
        nodes = {n for n in path if n != client}
        common = nodes if common is None else common & nodes
    if not common:
        return []
    # Stable order: prefer suppliers, then topological-ish by first appearance
    order: list[str] = []
    for s in suppliers:
        if s in common:
            order.append(s)
    for n in sorted(common):
        if n not in order:
            order.append(n)
    return order


def _apparent_route_count(graph: nx.DiGraph, suppliers: Iterable[str], client: str) -> int:
    total = 0
    for s in suppliers:
        if s not in graph:
            continue
        try:
            total += sum(1 for _ in nx.all_simple_paths(graph, s, client))
        except (nx.NetworkXError, nx.NodeNotFound):
            continue
    return total


def count_optionality(graph: nx.DiGraph) -> tuple[int, list[list[str]]]:
    client = client_id(graph)
    suppliers = [s for s in supplier_ids(graph) if s in graph]
    if client not in graph or not suppliers:
        return 0, []
    o = _max_node_disjoint(graph, suppliers, client)
    paths = _pack_paths(graph, suppliers, client, o)
    return o, paths


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

    client = client_id(graph)
    suppliers = supplier_ids(graph)
    o, paths = count_optionality(g)
    drivers = [f"path{i}:" + "→".join(p) for i, p in enumerate(paths, 1)]

    # Name shared nodes that collapse apparent multi-route topology.
    apparent = _apparent_route_count(g, suppliers, client)
    if apparent > o:
        for node in _nodes_on_all_paths(g, suppliers, client):
            drivers.append(f"shared_collapse:{node}")

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(o),
        status=_status(o, thresholds),
        drivers=drivers,
        inputs={
            "paths": paths,
            "client_id": client,
            "suppliers": suppliers,
            "apparent_routes": apparent,
        },
        meaning=(
            f"{o} node-disjoint supply path(s) to the client "
            "(shared sources and internal nodes collapse corridors). "
            "More paths mean more structural ways out. "
            "Counts topology only — not path-usage forecasts."
        ),
        unit="paths",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Count node-disjoint supply paths (Menger / max-flow; structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
