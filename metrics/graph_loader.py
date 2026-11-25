"""Load a YAML dependency graph into a networkx DiGraph.

Node kinds: supplier, asset, route, buyer.
Edge attributes: share, flow, capacity, buffer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from metrics.contracts import DependencyGraphSpec, NodeKind


def load_graph_spec(path: str | Path) -> DependencyGraphSpec:
    """Parse YAML into a validated DependencyGraphSpec."""
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"graph YAML must be a mapping, got {type(data).__name__}")
    return DependencyGraphSpec.model_validate(data)


def spec_to_networkx(spec: DependencyGraphSpec) -> nx.DiGraph:
    """Build a directed NetworkX graph from a DependencyGraphSpec."""
    g = nx.DiGraph(name=spec.name, client_id=spec.client_id)
    if spec.survival_floor is not None:
        g.graph["survival_floor"] = float(spec.survival_floor)
    if spec.inputs:
        g.graph["inputs"] = [inp.model_dump(mode="json") for inp in spec.inputs]
    if spec.ruin_line is not None:
        g.graph["ruin_line"] = spec.ruin_line.model_dump(mode="json")
    # Optional financial sections (ADR-019). Absent keys mean section omitted.
    if spec.liquidity is not None:
        g.graph["liquidity"] = spec.liquidity.model_dump(mode="json")
    if spec.covenants:
        g.graph["covenants"] = [c.model_dump(mode="json") for c in spec.covenants]
    if spec.contracts:
        g.graph["contracts"] = [c.model_dump(mode="json") for c in spec.contracts]
    if spec.customers:
        g.graph["customers"] = [c.model_dump(mode="json") for c in spec.customers]
    if spec.energy is not None:
        g.graph["energy"] = spec.energy.model_dump(mode="json")
    for node in spec.nodes:
        g.add_node(
            node.id,
            kind=node.kind.value if isinstance(node.kind, NodeKind) else node.kind,
            type=node.type,
            region=node.region,
            technology=node.technology,
            critical=bool(node.critical),
            **{k: v for k, v in node.attributes.items() if k not in {"type", "region", "technology"}},
        )
    node_ids = set(g.nodes)
    for edge in spec.edges:
        if edge.source not in node_ids:
            raise ValueError(f"edge source {edge.source!r} not in nodes")
        if edge.target not in node_ids:
            raise ValueError(f"edge target {edge.target!r} not in nodes")
        attrs: dict[str, Any] = {
            "share": float(edge.share),
            "flow": float(edge.flow),
            "capacity": float(edge.capacity),
            "buffer": float(edge.buffer),
        }
        if edge.stress_response:
            attrs["stress_response"] = edge.stress_response
        g.add_edge(edge.source, edge.target, **attrs)
    return g


def load_graph(path: str | Path) -> nx.DiGraph:
    """Load YAML path → validated NetworkX DiGraph."""
    return spec_to_networkx(load_graph_spec(path))


def client_id(graph: nx.DiGraph) -> str:
    """Return the client/buyer node id stored on the graph."""
    cid = graph.graph.get("client_id")
    if cid is not None:
        return cid
    buyers = [n for n, d in graph.nodes(data=True) if d.get("kind") == NodeKind.BUYER.value]
    if len(buyers) != 1:
        raise ValueError("cannot infer unique client_id from graph")
    return buyers[0]


def supplier_ids(graph: nx.DiGraph) -> list[str]:
    return [n for n, d in graph.nodes(data=True) if d.get("kind") == NodeKind.SUPPLIER.value]


def supplier_shares(graph: nx.DiGraph) -> dict[str, float]:
    """Map each supplier to its contribution share into the client.

    Uses edge `share` along paths when present; otherwise allocates by
    proportional flow reaching the client. Direct supplier→client edges
    use their share attribute; multi-hop graphs sum share (or flow) on
    edges that leave each supplier, normalised to 1.0 when possible.
    """
    suppliers = supplier_ids(graph)
    if not suppliers:
        return {}

    # Prefer explicit shares on edges leaving suppliers
    raw: dict[str, float] = {}
    for s in suppliers:
        total = 0.0
        for _, _, data in graph.out_edges(s, data=True):
            share = float(data.get("share") or 0.0)
            flow = float(data.get("flow") or 0.0)
            total += share if share > 0.0 else flow
        raw[s] = total

    ssum = sum(raw.values())
    if ssum <= 0.0:
        # Equal fallback so HHI still has a defined structural reading
        n = len(suppliers)
        return {s: 1.0 / n for s in suppliers}
    return {s: v / ssum for s, v in raw.items()}


def copy_graph(graph: nx.DiGraph) -> nx.DiGraph:
    return graph.copy()


def apply_node_shock(graph: nx.DiGraph, node_id: str, intensity: float) -> nx.DiGraph:
    """Return a copy where the node's outbound edges are degraded by intensity.

    intensity=1.0 removes the node entirely (structural cut).
    """
    g = copy_graph(graph)
    if node_id not in g:
        raise KeyError(f"node {node_id!r} not in graph")
    if intensity >= 1.0 - 1e-15:
        g.remove_node(node_id)
        return g
    factor = 1.0 - intensity
    for u, v, data in list(g.out_edges(node_id, data=True)):
        for key in ("flow", "capacity", "share", "buffer"):
            if key in data:
                data[key] = float(data[key]) * factor
    return g


def apply_edge_shock(
    graph: nx.DiGraph, source: str, target: str, intensity: float
) -> nx.DiGraph:
    g = copy_graph(graph)
    if not g.has_edge(source, target):
        raise KeyError(f"edge {source!r}→{target!r} not in graph")
    if intensity >= 1.0 - 1e-15:
        g.remove_edge(source, target)
        return g
    factor = 1.0 - intensity
    data = g[source][target]
    for key in ("flow", "capacity", "share", "buffer"):
        if key in data:
            data[key] = float(data[key]) * factor
    return g


def deliverable_flow(graph: nx.DiGraph, sink: str | None = None) -> float:
    """Structural deliverable flow into the client: sum of inbound edge flows.

    This is a graph accounting identity, not a forecast of realised volume.
    """
    sink = sink or client_id(graph)
    if sink not in graph:
        return 0.0
    return float(sum(d.get("flow", 0.0) for _, _, d in graph.in_edges(sink, data=True)))


def edge_key(u: str, v: str) -> str:
    return f"{u}->{v}"


def graph_summary(graph: nx.DiGraph) -> dict[str, Any]:
    return {
        "name": graph.graph.get("name"),
        "client_id": client_id(graph),
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "suppliers": supplier_ids(graph),
    }
