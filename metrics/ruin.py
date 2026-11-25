"""Ruin: whether an explicit stress probe crosses a point of no return.

Formula
-------
When an **explicit** probe is configured (scenario node/edge shocks,
``scenario.run_stress_ladder``, or an explicit ``ladder=`` argument),
using the stress ladder δ ∈ {0.10, 0.20, 0.50} by default (or scenario
override):

    F₀ = deliverable inbound flow to the client
    F(δ) = deliverable flow after structural stress at intensity δ

Survival floor resolution (first match wins):

    1. ``scenario.survival_floor`` (also set by CLI ``--survival-floor``)
    2. graph YAML / ``graph.graph["survival_floor"]`` (client-level override)
    3. ``thresholds.ruin.survival_floor`` (documented default **0.5**)

Ruin iff any δ in the ladder satisfies:

    F(δ) < floor × F₀     when F₀ > 0
    or F₀ ≤ 0             (no deliverable baseline)

Strict inequality: remaining exactly equal to the floor is not ruin.

Debt covenants (optional ``covenants`` section, ADR-019) are additional
ruin lines. At each probe intensity δ, each covenant's ``current`` is
moved toward breach by δ × cited ``worst_on_record`` on its linked
stress input. The **first** line to breach — a covenant id or the
survival floor — is reported. Missing covenant ``current`` values are
flagged fragile (ruin red), never silently treated as safe.

When **no** explicit probe is configured, status is ``NOT_TESTED`` —
silence is not safety. An untested company must never look GREEN.

Value = 1.0 if ruin, else 0.0 (and 0.0 when not tested).

Meaning
-------
Ruin is a hard structural red flag: under an explicit stress probe,
deliverable flow falls below the client's survival floor and/or a debt
covenant is breached. This is not a probability of ruin — it flags that
the graph's accounting admits a below-line state at a listed stress
intensity.

Status
------
  not_tested  if no explicit shock / ladder probe is configured
  red         if ruin
  green       otherwise (explicitly tested and all lines held)

``run_all`` forces the Convexity group to red whenever ruin is red.
``NOT_TESTED`` is never counted as a pass.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.finance import (
    covenant_breached,
    covenant_stressed_value,
    graph_covenants,
    has_covenants,
    input_worst_on_record,
)
from metrics.graph_loader import (
    apply_edge_shock,
    apply_node_shock,
    client_id,
    deliverable_flow,
)
from metrics.stress import ensure_flow, stress_ladder_losses
from metrics.thresholds import STRESS_LADDER, THRESHOLDS, Thresholds

METRIC = "ruin"
VERSION = "3.0.0"


def resolve_survival_floor(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> float:
    """Resolve survival floor: scenario → graph YAML → thresholds default."""
    thresholds = thresholds or THRESHOLDS
    if scenario is not None and scenario.survival_floor is not None:
        return float(scenario.survival_floor)
    graph_floor = graph.graph.get("survival_floor")
    if graph_floor is not None:
        return float(graph_floor)
    ruin_line = graph.graph.get("ruin_line") or {}
    if isinstance(ruin_line, dict) and ruin_line.get("survival_floor") is not None:
        return float(ruin_line["survival_floor"])
    return float(thresholds.ruin.survival_floor)


def has_explicit_probe(
    scenario: Scenario | None,
    ladder: tuple[float, ...] | None = None,
) -> bool:
    """True when the caller opted into a ruin probe (shocks or ladder)."""
    if ladder is not None:
        return True
    if scenario is None:
        return False
    if scenario.run_stress_ladder:
        return True
    if scenario.node_shocks or scenario.edge_shocks:
        return True
    if scenario.stress_ladder:
        return True
    return False


def _resolve_ladder(
    scenario: Scenario,
    ladder: tuple[float, ...] | None,
) -> tuple[float, ...]:
    if ladder is not None:
        return ladder
    if scenario.stress_ladder:
        return tuple(float(x) for x in scenario.stress_ladder)
    return STRESS_LADDER


def _apply_shocks(graph: nx.DiGraph, scenario: Scenario) -> nx.DiGraph:
    g = graph
    for ns in scenario.node_shocks:
        if ns.node_id in g:
            g = apply_node_shock(g, ns.node_id, ns.intensity)
    for es in scenario.edge_shocks:
        if g.has_edge(es.source, es.target):
            g = apply_edge_shock(g, es.source, es.target, es.intensity)
    return g


def _check_covenants_at_delta(
    graph: nx.DiGraph, delta: float
) -> tuple[list[str], list[str]]:
    """Return (breached_covenant_ids, unknown_fragile_ids) at intensity δ."""
    breached: list[str] = []
    unknown: list[str] = []
    if not has_covenants(graph):
        return breached, unknown
    for cov in graph_covenants(graph):
        if cov.current is None:
            unknown.append(cov.id)
            continue
        wor, _ = input_worst_on_record(graph, cov.stress_input_id)
        if wor is None or wor <= 0:
            # Covenant present but no cited swing → fragile unknown.
            unknown.append(cov.id)
            continue
        stressed = covenant_stressed_value(cov, float(delta) * float(wor))
        if stressed is not None and covenant_breached(cov, stressed):
            breached.append(cov.id)
    return breached, unknown


def _result(
    *,
    is_ruin: bool,
    crossed: list[str],
    f0: float,
    remaining: dict,
    losses: dict,
    floor: float,
    probe: str,
    first_breach: str | None = None,
    covenant_breaches: list[str] | None = None,
    unknown_covenants: list[str] | None = None,
) -> MetricResult:
    covenant_breaches = covenant_breaches or []
    unknown_covenants = unknown_covenants or []
    drivers = list(crossed) if is_ruin else []
    if first_breach:
        drivers = [f"first_breach:{first_breach}", *drivers]
    for cid in covenant_breaches:
        if f"covenant:{cid}" not in drivers:
            drivers.append(f"covenant:{cid}")
    for cid in unknown_covenants:
        drivers.append(f"unknown_covenant:{cid}")
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=1.0 if is_ruin else 0.0,
        status=Status.RED if is_ruin else Status.GREEN,
        drivers=drivers,
        inputs={
            "F0": f0,
            "remaining": {str(k): v for k, v in remaining.items()},
            "losses": {str(k): v for k, v in losses.items()},
            "survival_floor": floor,
            "threshold_flow": floor * f0 if f0 > 0 else 0.0,
            "crossed_rungs": crossed,
            "probe": probe,
            "first_breach": first_breach,
            "covenant_breaches": covenant_breaches,
            "unknown_covenants": unknown_covenants,
        },
        meaning=(
            (
                f"RUIN: first breach={first_breach or 'survival_floor'}. "
                if is_ruin
                else "Explicit probe: survival floor and covenants held. "
            )
            + f"Floor={floor:.2f} of baseline. Hard structural flag — not a probability of ruin."
        ),
        unit="flag",
    )


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    ladder: tuple[float, ...] | None = None,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    scenario = scenario or Scenario()

    if not has_explicit_probe(scenario, ladder):
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={
                "reason": "no_explicit_shock",
                "hint": (
                    "Set scenario.run_stress_ladder, pass ladder=, "
                    "or configure node/edge shocks."
                ),
            },
            meaning=(
                "NOT TESTED: no explicit shock or stress-ladder probe configured. "
                "Silence is not safety — ruin is untested, not green."
            ),
            unit="flag",
        )

    floor = resolve_survival_floor(graph, scenario, thresholds)
    use_ladder = _resolve_ladder(scenario, ladder)
    wants_ladder = (
        scenario.run_stress_ladder
        or scenario.stress_ladder is not None
        or ladder is not None
    )
    has_shocks = bool(scenario.node_shocks or scenario.edge_shocks)

    g = ensure_flow(_apply_shocks(graph, scenario))
    sink = client_id(graph)
    f0_intact = deliverable_flow(ensure_flow(graph), sink)

    if has_shocks and not wants_ladder:
        f_shocked = deliverable_flow(g, sink if sink in g else None)
        remaining = {"shocked": f_shocked}
        losses = {"shocked": max(f0_intact - f_shocked, 0.0)}
        crossed: list[str] = []
        first_breach: str | None = None
        # Shock intensity: use max node/edge shock as δ for covenant scan.
        shock_delta = 0.0
        for ns in scenario.node_shocks:
            shock_delta = max(shock_delta, float(ns.intensity))
        for es in scenario.edge_shocks:
            shock_delta = max(shock_delta, float(es.intensity))
        cov_hit, cov_unknown = _check_covenants_at_delta(graph, shock_delta)
        if cov_unknown:
            # Present but unknowable covenant → fragile ruin flag.
            return _result(
                is_ruin=True,
                crossed=["unknown_covenant"],
                f0=f0_intact,
                remaining=remaining,
                losses=losses,
                floor=floor,
                probe="shock",
                first_breach=f"unknown_covenant:{cov_unknown[0]}",
                covenant_breaches=cov_hit,
                unknown_covenants=cov_unknown,
            )
        if cov_hit and first_breach is None:
            first_breach = f"covenant:{cov_hit[0]}"
            crossed.append("shocked")
        if f0_intact <= 0 or f_shocked < floor * f0_intact:
            crossed = list(dict.fromkeys([*crossed, "shocked"]))
            if first_breach is None:
                first_breach = "survival_floor"
        return _result(
            is_ruin=len(crossed) > 0 or bool(cov_hit),
            crossed=crossed,
            f0=f0_intact,
            remaining=remaining,
            losses=losses,
            floor=floor,
            probe="shock",
            first_breach=first_breach,
            covenant_breaches=cov_hit,
            unknown_covenants=cov_unknown,
        )

    # Ladder probe (optionally after shocks)
    f0, remaining, losses = stress_ladder_losses(g, use_ladder)
    crossed = []
    first_breach = None
    all_cov_hits: list[str] = []
    all_cov_unknown: list[str] = []
    if f0 <= 0:
        crossed = [f"delta={d}" for d in use_ladder]
        first_breach = "survival_floor"
    else:
        threshold_flow = floor * f0
        for delta in use_ladder:
            f = remaining[delta]
            cov_hit, cov_unknown = _check_covenants_at_delta(graph, float(delta))
            all_cov_unknown.extend(cov_unknown)
            if cov_unknown and first_breach is None:
                first_breach = f"unknown_covenant:{cov_unknown[0]}"
                crossed.append(f"delta={delta}")
            if cov_hit:
                all_cov_hits.extend(cov_hit)
                if first_breach is None:
                    first_breach = f"covenant:{cov_hit[0]}"
                crossed.append(f"delta={delta}")
            if f < threshold_flow:
                crossed.append(f"delta={delta}")
                if first_breach is None:
                    first_breach = "survival_floor"

    # Deduplicate while preserving order
    crossed = list(dict.fromkeys(crossed))
    all_cov_hits = list(dict.fromkeys(all_cov_hits))
    all_cov_unknown = list(dict.fromkeys(all_cov_unknown))
    is_ruin = len(crossed) > 0 or bool(all_cov_hits) or bool(all_cov_unknown)
    if all_cov_unknown and first_breach is None:
        first_breach = f"unknown_covenant:{all_cov_unknown[0]}"

    return _result(
        is_ruin=is_ruin,
        crossed=crossed,
        f0=f0,
        remaining=remaining,
        losses=losses,
        floor=floor,
        probe="shock+ladder" if has_shocks else "ladder",
        first_breach=first_breach,
        covenant_breaches=all_cov_hits,
        unknown_covenants=all_cov_unknown,
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Detect structural ruin on an explicit stress probe."
    )
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help=(
            "Ruin when remaining flow < FRAC × baseline F0 at any ladder rung. "
            "Overrides graph YAML and the default (0.5 in metrics.thresholds)."
        ),
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    # --stress-ladder is on common args and already folded into scenario
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
