"""Shared structural stress-ladder helpers.

Degrades edge deliverability under a shock intensity. This is a structural
probe of the graph's flow accounting — not a forecast of realised shocks.
"""

from __future__ import annotations

import networkx as nx

from metrics.graph_loader import client_id, copy_graph, deliverable_flow


def edge_remaining(
    flow: float,
    capacity: float,
    buffer: float,
    delta: float,
    stress_response: str = "buffered",
) -> float:
    """Remaining deliverable flow on one edge under intensity ``delta``.

    Profiles
    --------
    buffered (default)
        rem = min(flow, capacity * (1 - δ) + buffer)
        With buffer=0 and capacity=flow this is linear in δ.
        With buffer>0, early shocks are absorbed then loss accelerates
        (concave payoff → fragile).

    linear
        rem = flow * (1 - δ)

    decelerating
        rem = flow * (1 - δ)²
        Marginal loss shrinks with δ (convex payoff → antifragile).

    cliff
        rem = flow * (1 - δ) while δ < 0.5, else 0
        Forces a point-of-no-return at the 50% ladder rung.
    """
    delta = max(0.0, min(1.0, float(delta)))
    flow = float(flow)
    capacity = float(capacity)
    buffer = float(buffer)
    profile = (stress_response or "buffered").lower()

    if profile == "linear":
        return max(0.0, flow * (1.0 - delta))
    if profile == "decelerating":
        return max(0.0, flow * (1.0 - delta) ** 2)
    if profile == "cliff":
        if delta >= 0.5 - 1e-15:
            return 0.0
        return max(0.0, flow * (1.0 - delta))
    # buffered (default)
    shocked_cap = capacity * (1.0 - delta)
    return max(0.0, min(flow, shocked_cap + buffer))


def apply_uniform_stress(graph: nx.DiGraph, delta: float) -> nx.DiGraph:
    """Return a copy whose edge flows equal remaining deliverable under δ."""
    g = copy_graph(graph)
    for _u, _v, data in g.edges(data=True):
        flow = float(data.get("flow") or 0.0)
        # If flow is unset, fall back to share so empty-flow graphs still probe.
        if flow <= 0:
            flow = float(data.get("share") or 0.0)
        capacity = float(data.get("capacity") or 0.0)
        if capacity <= 0:
            capacity = flow
        buffer = float(data.get("buffer") or 0.0)
        profile = str(data.get("stress_response") or g.graph.get("stress_response") or "buffered")
        data["flow"] = edge_remaining(flow, capacity, buffer, delta, profile)
    return g


def ensure_flow(graph: nx.DiGraph) -> nx.DiGraph:
    g = copy_graph(graph)
    if deliverable_flow(g) > 0:
        return g
    for _u, _v, data in g.edges(data=True):
        share = float(data.get("share") or 0.0)
        if share > 0 and float(data.get("flow") or 0.0) <= 0:
            data["flow"] = share
            if float(data.get("capacity") or 0.0) < share:
                data["capacity"] = share
    return g


def stress_ladder_losses(
    graph: nx.DiGraph,
    ladder: tuple[float, ...],
) -> tuple[float, dict[float, float], dict[float, float]]:
    """Return (F0, remaining_by_delta, loss_by_delta)."""
    g0 = ensure_flow(graph)
    sink = client_id(g0)
    f0 = deliverable_flow(g0, sink)
    remaining: dict[float, float] = {}
    losses: dict[float, float] = {}
    for delta in ladder:
        g = apply_uniform_stress(g0, delta)
        f = deliverable_flow(g, sink if sink in g else None)
        remaining[delta] = f
        losses[delta] = max(f0 - f, 0.0)
    return f0, remaining, losses
