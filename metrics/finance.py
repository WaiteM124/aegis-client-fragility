"""Helpers for optional financial-side graph sections (ADR-019).

Cash/liquidity, covenants, contracts, customers, and energy are optional.
When a section is absent, related metrics return NOT_TESTED with
``optional_section_absent`` so group roll-up on supply-only graphs is
unchanged. When a section is present but a required field is missing,
metrics flag fragile — never silently default to a safe value.

Swing sizes always come from cited ``worst_on_record`` values. No
probabilities, no free sliders, no AI-set swings.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from metrics.contracts import (
    ContractSpec,
    CovenantKind,
    CovenantSpec,
    CustomerSpec,
    EnergySpec,
    LiquiditySpec,
    MetricResult,
    Status,
)


def graph_liquidity(graph: nx.DiGraph) -> LiquiditySpec | None:
    raw = graph.graph.get("liquidity")
    if raw is None:
        return None
    return LiquiditySpec.model_validate(raw)


def graph_covenants(graph: nx.DiGraph) -> list[CovenantSpec]:
    raw = graph.graph.get("covenants") or []
    return [CovenantSpec.model_validate(item) for item in raw]


def graph_contracts(graph: nx.DiGraph) -> list[ContractSpec]:
    raw = graph.graph.get("contracts") or []
    return [ContractSpec.model_validate(item) for item in raw]


def graph_customers(graph: nx.DiGraph) -> list[CustomerSpec]:
    raw = graph.graph.get("customers") or []
    return [CustomerSpec.model_validate(item) for item in raw]


def graph_energy(graph: nx.DiGraph) -> EnergySpec | None:
    raw = graph.graph.get("energy")
    if raw is None:
        return None
    return EnergySpec.model_validate(raw)


def has_customers(graph: nx.DiGraph) -> bool:
    return bool(graph.graph.get("customers"))


def has_liquidity(graph: nx.DiGraph) -> bool:
    return graph.graph.get("liquidity") is not None


def has_covenants(graph: nx.DiGraph) -> bool:
    return bool(graph.graph.get("covenants"))


def has_energy(graph: nx.DiGraph) -> bool:
    return graph.graph.get("energy") is not None


def has_contracts(graph: nx.DiGraph) -> bool:
    return bool(graph.graph.get("contracts"))


def section_absent_result(
    *,
    metric: str,
    version: str,
    section: str,
    unit: str | None = None,
) -> MetricResult:
    """NOT_TESTED result when an optional financial section is omitted."""
    return MetricResult(
        metric=metric,
        version=version,
        value=0.0,
        status=Status.NOT_TESTED,
        drivers=[],
        inputs={
            "reason": "optional_section_absent",
            "optional_section_absent": True,
            "section": section,
        },
        meaning=(
            f"NOT TESTED: optional '{section}' section absent on this graph. "
            "Supply-only graphs keep identical group status; absence is not a pass."
        ),
        unit=unit,
    )


def available_liquidity(liq: LiquiditySpec) -> tuple[float | None, list[str]]:
    """Return (available_liquidity, unknown_fields).

    available = cash_on_hand + sum(undrawn facilities). Missing cash is
    unknown (fragile); facilities may be empty.
    """
    unknown: list[str] = []
    if liq.cash_on_hand is None:
        unknown.append("cash_on_hand")
        cash = 0.0
    else:
        cash = float(liq.cash_on_hand)
    undrawn = 0.0
    for fac in liq.committed_facilities:
        undrawn += float(fac.undrawn)
    if unknown:
        return None, unknown
    return cash + undrawn, unknown


def customer_shares(customers: list[CustomerSpec]) -> dict[str, float]:
    """Normalise declared customer revenue shares to sum to 1 when possible."""
    raw = {c.id: float(c.revenue_share) for c in customers}
    total = sum(raw.values())
    if total <= 0.0:
        n = len(customers)
        if n == 0:
            return {}
        return {c.id: 1.0 / n for c in customers}
    return {cid: v / total for cid, v in raw.items()}


def input_worst_on_record(
    graph: nx.DiGraph, input_id: str | None
) -> tuple[float | None, dict[str, Any] | None]:
    """Look up a named graph input's worst_on_record (cited swing size)."""
    if not input_id:
        return None, None
    for item in graph.graph.get("inputs") or []:
        if str(item.get("id")) == input_id:
            wor = item.get("worst_on_record")
            return (float(wor) if wor is not None else None), dict(item)
    return None, None


def covenant_headroom(covenant: CovenantSpec) -> tuple[float | None, str | None]:
    """Positive headroom to breach, or (None, reason) when unknown/already breached.

    max covenant: headroom = limit − current (breach when current rises).
    min covenant: headroom = current − limit (breach when current falls).
    """
    if covenant.current is None:
        return None, "missing_current"
    current = float(covenant.current)
    limit = float(covenant.limit)
    kind = (
        covenant.kind
        if isinstance(covenant.kind, CovenantKind)
        else CovenantKind(covenant.kind)
    )
    if kind == CovenantKind.MAX:
        return limit - current, None
    return current - limit, None


def covenant_stressed_value(
    covenant: CovenantSpec, intensity: float
) -> float | None:
    """Move ``current`` toward breach by ``intensity`` × swing units.

    Intensity here is already in covenant-metric units (multiple × WOR),
    not a probability. max → current rises; min → current falls.
    """
    if covenant.current is None:
        return None
    current = float(covenant.current)
    kind = (
        covenant.kind
        if isinstance(covenant.kind, CovenantKind)
        else CovenantKind(covenant.kind)
    )
    delta = abs(float(intensity))
    if kind == CovenantKind.MAX:
        return current + delta
    return current - delta


def covenant_breached(covenant: CovenantSpec, value: float) -> bool:
    kind = (
        covenant.kind
        if isinstance(covenant.kind, CovenantKind)
        else CovenantKind(covenant.kind)
    )
    limit = float(covenant.limit)
    if kind == CovenantKind.MAX:
        return value > limit + 1e-15
    return value < limit - 1e-15


def unrecovered_energy_share(energy: EnergySpec) -> tuple[float | None, list[str]]:
    """cost_share × (1 − pass_through). Missing fields → unknown list."""
    unknown: list[str] = []
    if energy.cost_share is None:
        unknown.append("cost_share")
    if energy.pass_through_pct is None:
        unknown.append("pass_through_pct")
    if unknown:
        return None, unknown
    assert energy.cost_share is not None
    assert energy.pass_through_pct is not None
    return float(energy.cost_share) * (1.0 - float(energy.pass_through_pct)), unknown


def fixed_price_input_exposed_contracts(
    contracts: list[ContractSpec],
) -> list[ContractSpec]:
    from metrics.contracts import PricingKind

    out: list[ContractSpec] = []
    for c in contracts:
        pricing = c.pricing if isinstance(c.pricing, PricingKind) else PricingKind(c.pricing)
        if pricing == PricingKind.FIXED and c.input_cost_exposed:
            out.append(c)
    return out
