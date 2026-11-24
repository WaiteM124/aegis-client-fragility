"""Single points of failure: nodes whose removal disconnects supply from the client.

Formula
-------
Let S be the set of supplier nodes and c the client (buyer).
A non-client node v is a single point of failure (SPOF) if:

    • there exists at least one directed path from some s ∈ S to c in G, and
    • after removing v, there is no directed path from any s ∈ S \\ {v} to c.

Value = number of SPOFs.

Meaning
-------
A SPOF is a structural cut-vertex on the supply→client connectivity.
Removing it isolates the client from all suppliers. This identifies
where the graph is brittle; it does not estimate the chance of removal.

Status defaults
---------------
  green  if count = 0
  amber  if count = 1
  red    if count ≥ 2
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import client_id, supplier_ids
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "single_points_of_failure"
VERSION = "1.0.0"


def _has_supply_path(graph: nx.DiGraph, suppliers: list[str], client: str) -> bool:
    if client not in graph:
        return False
    for s in suppliers:
        if s not in graph:
            continue
        if nx.has_path(graph, s, client):
            return True
    return False


def find_spofs(graph: nx.DiGraph) -> list[str]:
    client = client_id(graph)
    suppliers = supplier_ids(graph)
    if not _has_supply_path(graph, suppliers, client):
        # Already disconnected — every remaining intermediate is moot;
        # report no SPOF on an already-failed structure.
        return []

    spofs: list[str] = []
    candidates = [n for n in graph.nodes if n != client]
    for v in candidates:
        g2 = graph.copy()
        g2.remove_node(v)
        remaining_suppliers = [s for s in suppliers if s != v]
        if not _has_supply_path(g2, remaining_suppliers, client):
            spofs.append(v)
    return sorted(spofs)


def _status(count: int, thresholds: Thresholds) -> Status:
    t = thresholds.spof
    if count <= t.green_max:
        return Status.GREEN
    if count <= t.amber_max:
        return Status.AMBER
    return Status.RED


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    """Identify SPOFs on the graph, optionally after applying scenario shocks first."""
    thresholds = thresholds or THRESHOLDS
    g = graph
    if scenario is not None:
        from metrics.graph_loader import apply_edge_shock, apply_node_shock

        for ns in scenario.node_shocks:
            if ns.node_id in g:
                g = apply_node_shock(g, ns.node_id, ns.intensity)
        for es in scenario.edge_shocks:
            if g.has_edge(es.source, es.target):
                g = apply_edge_shock(g, es.source, es.target, es.intensity)

    spofs = find_spofs(g)
    count = len(spofs)
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(count),
        status=_status(count, thresholds),
        drivers=spofs,
        inputs={"spofs": spofs, "client_id": client_id(graph), "suppliers": supplier_ids(graph)},
        meaning=(
            f"{count} single point(s) of failure. "
            "Each listed node cuts all supplier→client paths when removed. "
            "Structural cut set; not a failure probability."
        ),
        unit="count",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Find single points of failure (structural).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
