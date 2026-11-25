"""Convexity / fragility from model output via symmetric second differences.

Formula
-------
For each named graph input with a ``worst_on_record`` move W, evaluate harm
(loss of deliverable flow, or an injected ``harm_fn``) on a scan grid of
step sizes anchored on W:

    d ∈ {0.25, 0.5, 1.0, 1.5, 2.0} × W

These are a scan grid, not scenarios — no likelihoods are attached.

At centre x = W (the record move), the symmetric second difference is:

    Δ²(d) = harm(clamp(x+d)) + harm(clamp(x-d)) − 2 · harm(x)

Bounded inputs are clamped to ``[lower_bound, upper_bound]``; clamping
sites are reported. A large relative jump between neighbouring grid
points is reported separately as a **cliff** (threshold), distinct from
smooth curvature.

Classification (from mean Δ² across usable step sizes, scaled by F₀ when
using graph harm):
  clearly positive → FRAGILE   (harm accelerates)
  near zero        → ROBUST
  clearly negative → ANTIFRAGILE (own flag — not merely green)

Value reported = mean curvature.

Meaning
-------
Taleb's structural fragility heuristic measured from the model's actual
output curve — never from declared edge ``stress_response`` labels.
Labels may remain as modelling inputs that shape the flow response, but
tests must not assert label equals shape. Property of the response under
a worst-on-record-anchored scan grid, not a forecast of which shock arrives.

Status
------
  not_tested  if no inputs / worst_on_record missing
  red/amber   if fragile (curvature clearly positive)
  green       if robust or antifragile
  antifragile is also reported via ``inputs["antifragile_flag"]=True``
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock, deliverable_flow
from metrics.stress import apply_uniform_stress, ensure_flow
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "convexity"
VERSION = "2.0.0"


def _graph_inputs(graph: nx.DiGraph) -> list[dict[str, Any]]:
    raw = graph.graph.get("inputs") or []
    return [dict(item) for item in raw]


def _clamp(value: float, lo: float | None, hi: float | None) -> tuple[float, bool]:
    v = float(value)
    clamped = False
    if lo is not None and v < lo:
        v = float(lo)
        clamped = True
    if hi is not None and v > hi:
        v = float(hi)
        clamped = True
    return v, clamped


def _default_harm_fn(graph: nx.DiGraph) -> Callable[[float], float]:
    g0 = ensure_flow(graph)
    f0 = deliverable_flow(g0)

    def harm(intensity: float) -> float:
        # Intensity is treated as uniform edge-stress δ ∈ [0, 1] after clamp.
        delta = max(0.0, float(intensity))
        g = apply_uniform_stress(g0, delta)
        f = deliverable_flow(g)
        return max(f0 - f, 0.0)

    return harm


def _classify(
    curvature: float,
    thresholds: Thresholds,
    *,
    scale: float,
) -> tuple[Status, str]:
    t = thresholds.convexity
    # Scale-aware tolerances when harm is in flow units
    tol = t.linear_tol * max(scale, 1.0)
    red_min = t.red_min * max(scale, 1.0)
    if curvature < -tol:
        return Status.GREEN, "antifragile"
    if abs(curvature) <= tol:
        return Status.GREEN, "robust"
    if curvature > red_min:
        return Status.RED, "fragile"
    return Status.AMBER, "fragile"


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    harm_fn: Callable[[float], float] | None = None,
) -> MetricResult:
    """Measure harm curvature from model output (not from labels)."""
    thresholds = thresholds or THRESHOLDS
    t = thresholds.convexity

    g = graph
    if scenario is not None:
        for ns in scenario.node_shocks:
            if ns.node_id in g:
                g = apply_node_shock(g, ns.node_id, ns.intensity)
        for es in scenario.edge_shocks:
            if g.has_edge(es.source, es.target):
                g = apply_edge_shock(g, es.source, es.target, es.intensity)

    inputs = _graph_inputs(g)
    if not inputs:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={"reason": "no_graph_inputs"},
            meaning=(
                "NOT TESTED: graph has no named inputs with worst_on_record. "
                "Convexity needs an anchored scan grid — not a silent default ladder."
            ),
            unit="curvature",
        )

    harm = harm_fn if harm_fn is not None else _default_harm_fn(g)
    f0 = deliverable_flow(ensure_flow(g))
    scale = f0 if harm_fn is None else 1.0

    per_input: dict[str, Any] = {}
    all_curvatures: list[float] = []
    all_cliffs: list[dict[str, Any]] = []
    all_clamped: list[dict[str, Any]] = []
    missing: list[str] = []

    for inp in inputs:
        inp_id = str(inp.get("id") or "unnamed")
        wor = inp.get("worst_on_record")
        if wor is None:
            missing.append(inp_id)
            per_input[inp_id] = {
                "status": Status.NOT_TESTED.value,
                "reason": "missing_worst_on_record",
            }
            continue

        w = float(wor)
        lo = inp.get("lower_bound")
        hi = inp.get("upper_bound")
        lo_f = float(lo) if lo is not None else None
        hi_f = float(hi) if hi is not None else None

        # Scan grid of absolute intensities (multiples of W), plus centre
        multiples = (0.0,) + tuple(t.step_multiples)
        grid_raw = [m * w for m in multiples]
        grid: list[float] = []
        clamped_points: list[dict[str, Any]] = []
        for raw in grid_raw:
            val, was_clamped = _clamp(raw, lo_f, hi_f)
            grid.append(val)
            clamped_points.append(
                {
                    "input": inp_id,
                    "requested": raw,
                    "used": val,
                    "clamped": was_clamped,
                }
            )
            if was_clamped:
                all_clamped.append(clamped_points[-1])

        harms = [float(harm(x)) for x in grid]

        # Cliff detection between neighbouring distinct grid points
        cliffs: list[dict[str, Any]] = []
        for i in range(len(grid) - 1):
            dx = grid[i + 1] - grid[i]
            if abs(dx) < 1e-15:
                continue
            jump = harms[i + 1] - harms[i]
            # Relative to local harm scale (or unit scale for synthetic harm_fn)
            ref = max(abs(harms[i]), abs(harms[i + 1]), abs(scale), 1e-15)
            if abs(jump) / ref >= t.cliff_rel_jump and abs(jump) > 1e-12:
                cliffs.append(
                    {
                        "input": inp_id,
                        "from": grid[i],
                        "to": grid[i + 1],
                        "harm_from": harms[i],
                        "harm_to": harms[i + 1],
                        "jump": jump,
                    }
                )
        all_cliffs.extend(cliffs)

        # Symmetric second differences at centre x = W
        x_center = w
        x_c, _ = _clamp(x_center, lo_f, hi_f)
        h_c = float(harm(x_c))
        curvatures: list[float] = []
        details: list[dict[str, Any]] = []
        for mult in t.step_multiples:
            d = mult * w
            if d <= 0:
                continue
            xp, cp = _clamp(x_c + d, lo_f, hi_f)
            xm, cm = _clamp(x_c - d, lo_f, hi_f)
            # Skip degenerate probes where both sides collapsed to the centre
            if abs(xp - x_c) < 1e-15 and abs(xm - x_c) < 1e-15:
                continue
            h_p = float(harm(xp))
            h_m = float(harm(xm))
            # Standard symmetric second difference (not divided by d² —
            # sign and relative magnitude are what classify shape).
            second = h_p + h_m - 2.0 * h_c
            # If clamping collapsed one side, still record but mark it.
            details.append(
                {
                    "d": d,
                    "multiple": mult,
                    "x": x_c,
                    "x_plus": xp,
                    "x_minus": xm,
                    "second_diff": second,
                    "clamped_plus": cp,
                    "clamped_minus": cm,
                }
            )
            # Only average probes where neither side was clamped and both
            # sides sit off the centre. Clamping breaks symmetry and would
            # falsely mark a linear response as curved.
            if (
                not cp
                and not cm
                and abs(xp - x_c) > 1e-15
                and abs(xm - x_c) > 1e-15
            ):
                curvatures.append(second)

        mean_curv = sum(curvatures) / len(curvatures) if curvatures else 0.0
        all_curvatures.append(mean_curv)
        status_i, shape_i = _classify(mean_curv, thresholds, scale=scale)
        per_input[inp_id] = {
            "worst_on_record": w,
            "mean_curvature": mean_curv,
            "shape": shape_i,
            "status": status_i.value,
            "second_differences": details,
            "grid": grid,
            "harms": harms,
            "cliffs": cliffs,
            "clamped_points": clamped_points,
        }

    if missing and not all_curvatures:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=missing,
            inputs={"reason": "missing_worst_on_record", "per_input": per_input},
            meaning=(
                "NOT TESTED: worst_on_record missing for all inputs. "
                "Cannot anchor the scan grid."
            ),
            unit="curvature",
        )

    if not all_curvatures:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={"reason": "no_usable_probes", "per_input": per_input},
            meaning="NOT TESTED: no usable second-difference probes after clamping.",
            unit="curvature",
        )

    # Never blend across inputs into a single fragility score for decisions:
    # report the worst shape by severity (fragile red > fragile amber >
    # robust > antifragile for "worst weakness" roll-up of THIS metric).
    mean_all = sum(all_curvatures) / len(all_curvatures)
    # Prefer the most fragile input's classification for status
    worst_status = Status.GREEN
    worst_shape = "robust"
    rank = {
        Status.GREEN: 0,
        Status.AMBER: 1,
        Status.RED: 2,
        Status.NOT_TESTED: -1,
    }
    antifragile_any = False
    for _iid, info in per_input.items():
        if info.get("shape") == "antifragile":
            antifragile_any = True
        st = Status(info["status"]) if info.get("status") in Status._value2member_map_ else Status.GREEN
        if rank.get(st, 0) > rank[worst_status]:
            worst_status = st
            worst_shape = str(info.get("shape") or "robust")
        elif info.get("shape") == "fragile" and worst_shape != "fragile":
            worst_shape = "fragile"

    # If everything is antifragile / robust, surface antifragile when present
    if worst_status == Status.GREEN and antifragile_any and worst_shape != "fragile":
        worst_shape = "antifragile"

    # Reconcile mean-based shape when single input
    if len(all_curvatures) == 1:
        worst_status, worst_shape = _classify(mean_all, thresholds, scale=scale)

    # Cliffs (threshold jumps) are reported separately from smooth curvature,
    # but they are still a fragility signal: elevate status at least to amber.
    if all_cliffs and worst_status in {Status.GREEN, Status.NOT_TESTED}:
        worst_status = Status.AMBER
        if worst_shape in {"robust", "antifragile"}:
            worst_shape = "fragile"

    drivers = [
        f"shape={worst_shape}",
        f"mean_curvature={mean_all:.6f}",
    ]
    if antifragile_any and worst_shape == "antifragile":
        drivers.append("ANTIFRAGILE")
    if all_cliffs:
        drivers.append(f"cliffs={len(all_cliffs)}")

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(mean_all),
        status=worst_status,
        drivers=drivers,
        inputs={
            "F0": f0,
            "shape": worst_shape,
            "antifragile_flag": bool(antifragile_any and worst_shape == "antifragile"),
            "mean_curvature": mean_all,
            "per_input": per_input,
            "cliffs": all_cliffs,
            "clamped_points": all_clamped,
            "step_multiples": list(t.step_multiples),
            "threshold_version": t.version,
        },
        meaning=(
            f"Payoff shape={worst_shape}; mean harm curvature={mean_all:.6f}. "
            "Measured from model output via symmetric second differences "
            "anchored on worst-on-record — not from declared labels. "
            "Scan grid has no likelihoods. Not an event forecast."
        ),
        unit="curvature",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description=(
            "Compute harm curvature from model output "
            "(symmetric second differences; no label circularity)."
        )
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
