"""Distance to ruin: smallest worst-on-record multiple that crosses a ruin line.

Formula
-------
For each named graph input with ``worst_on_record`` W and an explicit ruin
line (survival floor / covenant breach):

    1. Scan multiples m ∈ configured scan grid (default up to 5×).
    2. At intensity = clamp(m · W), evaluate remaining deliverable flow.
    3. Ruin when remaining < floor × F₀ (strict), or another configured line.
    4. Bisect between the last surviving multiple and the first failing one
       to refine the ruin multiple.

Debt covenants (optional ``covenants`` section, ADR-019) are additional
ruin lines. For each covenant with cited swing W on its linked stress
input, ruin_multiple = headroom / W. The **first** line to breach
(smallest multiple among survival floor and covenants) is reported;
lines are never averaged. Missing current or cited W → fragile.

Output per input / per covenant (never averaged — ruin is absorbing):
  - ruin_multiple, or null with "no ruin within scan range […]"
  - whether harm accelerates on the way (reuses convexity curvature sign)
  - ruin_cause (which line broke)

Status cut-offs from versioned ``DistanceToRuinThresholds``:
  red    if ruin_multiple ≤ red_max_multiple (default 1×)
  amber  if ruin_multiple ≤ amber_max_multiple (default 2×)
  green  if beyond amber, or no ruin within the stated scan range
  not_tested if ruin line or worst_on_record is missing

Overall status is the **worst** member (NOT_TESTED worse than green).

Meaning
-------
How many times the worst-on-record move fits before the company crosses a
configured ruin line (survival floor or debt covenant). Structural
accounting identity — not a probability of ruin.
"""

from __future__ import annotations

import argparse
from typing import Any

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.convexity import compute as compute_convexity
from metrics.finance import (
    covenant_headroom,
    graph_covenants,
    has_covenants,
    input_worst_on_record,
)
from metrics.graph_loader import apply_edge_shock, apply_node_shock, deliverable_flow
from metrics.ruin import resolve_survival_floor
from metrics.stress import apply_uniform_stress, ensure_flow
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "distance_to_ruin"
VERSION = "2.0.0"

_RANK = {
    Status.GREEN: 0,
    Status.NOT_TESTED: 1,
    Status.AMBER: 2,
    Status.RED: 3,
}


def _graph_inputs(graph: nx.DiGraph) -> list[dict[str, Any]]:
    return [dict(item) for item in (graph.graph.get("inputs") or [])]


def _clamp(value: float, lo: float | None, hi: float | None) -> float:
    v = float(value)
    if lo is not None and v < lo:
        v = float(lo)
    if hi is not None and v > hi:
        v = float(hi)
    return v


def _ruin_lines(
    graph: nx.DiGraph,
    scenario: Scenario | None,
    thresholds: Thresholds,
    *,
    require_explicit_ruin_line: bool,
) -> dict[str, float]:
    """Return named ruin-line fractions (remaining flow / F0)."""
    lines: dict[str, float] = {}
    ruin_line = graph.graph.get("ruin_line")
    if isinstance(ruin_line, dict):
        for key in ("survival_floor", "covenant_breach_flow_fraction"):
            if ruin_line.get(key) is not None:
                lines[key] = float(ruin_line[key])

    if require_explicit_ruin_line and not lines:
        return {}

    if "survival_floor" not in lines:
        # Fall back to resolved survival floor unless caller requires explicit
        if not require_explicit_ruin_line:
            lines["survival_floor"] = resolve_survival_floor(
                graph, scenario, thresholds
            )
    return lines


def _is_ruined(remaining: float, f0: float, lines: dict[str, float]) -> str | None:
    """Return the name of the first line that broke, or None."""
    if f0 <= 0:
        return next(iter(lines), "survival_floor")
    for name, floor in lines.items():
        if remaining < floor * f0:
            return name
    return None


def _status_for_multiple(
    multiple: float | None,
    thresholds: Thresholds,
    *,
    no_ruin_in_range: bool,
) -> Status:
    t = thresholds.distance_to_ruin
    if no_ruin_in_range:
        return Status.GREEN
    if multiple is None:
        return Status.NOT_TESTED
    if multiple <= t.red_max_multiple:
        return Status.RED
    if multiple <= t.amber_max_multiple:
        return Status.AMBER
    return Status.GREEN


def _harm_accelerates(graph: nx.DiGraph, scenario: Scenario | None, inp_id: str) -> bool | None:
    """Reuse convexity result: positive curvature ⇒ accelerates."""
    try:
        result = compute_convexity(graph, scenario)
    except Exception:
        return None
    if result.status == Status.NOT_TESTED:
        return None
    per = (result.inputs or {}).get("per_input") or {}
    info = per.get(inp_id) or {}
    shape = info.get("shape") or result.inputs.get("shape")
    if shape == "fragile":
        return True
    if shape in {"robust", "antifragile"}:
        return False
    curv = info.get("mean_curvature")
    if curv is None:
        curv = result.value
    return bool(curv > 0)


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    *,
    require_explicit_ruin_line: bool = False,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    t = thresholds.distance_to_ruin
    scenario = scenario or Scenario()

    g = graph
    for ns in scenario.node_shocks:
        if ns.node_id in g:
            g = apply_node_shock(g, ns.node_id, ns.intensity)
    for es in scenario.edge_shocks:
        if g.has_edge(es.source, es.target):
            g = apply_edge_shock(g, es.source, es.target, es.intensity)

    g0 = ensure_flow(g)
    f0 = deliverable_flow(g0)

    inputs = _graph_inputs(g0)
    lines = _ruin_lines(
        g0,
        scenario,
        thresholds,
        require_explicit_ruin_line=require_explicit_ruin_line,
    )
    covenants_present = has_covenants(g0)

    if not inputs and not covenants_present:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={"reason": "no_graph_inputs"},
            meaning=(
                "NOT TESTED: graph has no named inputs and no covenants. "
                "Distance to ruin needs per-input worst_on_record anchors."
            ),
            unit="multiple",
        )

    if not lines and not covenants_present:
        return MetricResult(
            metric=METRIC,
            version=VERSION,
            value=0.0,
            status=Status.NOT_TESTED,
            drivers=[],
            inputs={"reason": "missing_ruin_line"},
            meaning=(
                "NOT TESTED: ruin_line missing on graph. "
                "Configure ruin_line.survival_floor (or covenant) explicitly."
            ),
            unit="multiple",
        )

    per_input: dict[str, Any] = {}
    statuses: list[Status] = []
    drivers: list[str] = []
    # Track the smallest finite ruin multiple for the headline value
    headline_multiple: float | None = None

    scan_max = float(t.scan_max_multiple)
    scan_mults = [m for m in t.scan_multiples if m <= scan_max + 1e-15]
    if not scan_mults or scan_mults[-1] < scan_max:
        if scan_max not in scan_mults:
            scan_mults = list(scan_mults) + [scan_max]

    for inp in inputs:
        inp_id = str(inp.get("id") or "unnamed")
        wor = inp.get("worst_on_record")
        if wor is None:
            per_input[inp_id] = {
                "ruin_multiple": None,
                "report": "NOT_TESTED: missing worst_on_record",
                "ruin_cause": None,
                "harm_accelerates": None,
                "status": Status.NOT_TESTED.value,
            }
            statuses.append(Status.NOT_TESTED)
            drivers.append(f"{inp_id}:NOT_TESTED")
            continue

        w = float(wor)
        if w <= 0:
            per_input[inp_id] = {
                "ruin_multiple": None,
                "report": "NOT_TESTED: worst_on_record must be positive",
                "ruin_cause": None,
                "harm_accelerates": None,
                "status": Status.NOT_TESTED.value,
            }
            statuses.append(Status.NOT_TESTED)
            drivers.append(f"{inp_id}:NOT_TESTED")
            continue

        lo = inp.get("lower_bound")
        hi = inp.get("upper_bound")
        lo_f = float(lo) if lo is not None else None
        hi_f = float(hi) if hi is not None else None

        def remaining_at(multiple: float) -> tuple[float, str | None]:
            intensity = _clamp(multiple * w, lo_f, hi_f)
            stressed = apply_uniform_stress(g0, intensity)
            rem = deliverable_flow(stressed)
            cause = _is_ruined(rem, f0, lines)
            return rem, cause

        # Scan
        last_ok: float | None = 0.0
        first_fail: float | None = None
        first_cause: str | None = None
        for m in scan_mults:
            _rem, cause = remaining_at(m)
            if cause is not None:
                first_fail = m
                first_cause = cause
                break
            last_ok = m

        if first_fail is None:
            accelerates = _harm_accelerates(g0, scenario, inp_id)
            report = (
                f"no ruin within scan range [0, {scan_max}×] "
                f"of worst_on_record={w}"
            )
            st = _status_for_multiple(None, thresholds, no_ruin_in_range=True)
            per_input[inp_id] = {
                "ruin_multiple": None,
                "report": report,
                "ruin_cause": None,
                "harm_accelerates": accelerates,
                "status": st.value,
                "scan_max_multiple": scan_max,
                "worst_on_record": w,
            }
            statuses.append(st)
            drivers.append(f"{inp_id}:no_ruin_within_{scan_max}x")
            continue

        # Bisection refine between last_ok and first_fail
        lo_m = float(last_ok if last_ok is not None else 0.0)
        hi_m = float(first_fail)
        cause = first_cause
        for _ in range(t.bisection_iterations):
            mid = 0.5 * (lo_m + hi_m)
            _rem, mid_cause = remaining_at(mid)
            if mid_cause is not None:
                hi_m = mid
                cause = mid_cause
            else:
                lo_m = mid
        ruin_multiple = hi_m

        if headline_multiple is None or ruin_multiple < headline_multiple:
            headline_multiple = ruin_multiple

        accelerates = _harm_accelerates(g0, scenario, inp_id)
        st = _status_for_multiple(
            ruin_multiple, thresholds, no_ruin_in_range=False
        )
        per_input[inp_id] = {
            "ruin_multiple": ruin_multiple,
            "report": f"ruin at {ruin_multiple:.4f}× worst_on_record",
            "ruin_cause": cause,
            "harm_accelerates": accelerates,
            "status": st.value,
            "scan_max_multiple": scan_max,
            "worst_on_record": w,
        }
        statuses.append(st)
        drivers.append(f"{inp_id}:{ruin_multiple:.3f}x/{cause}")

    # Covenant ruin lines (ADR-019): distance = headroom / cited WOR.
    per_covenant: dict[str, Any] = {}
    first_breach: str | None = None
    first_breach_multiple: float | None = headline_multiple

    if has_covenants(g0):
        for cov in graph_covenants(g0):
            headroom, reason = covenant_headroom(cov)
            wor, _inp = input_worst_on_record(g0, cov.stress_input_id)
            if headroom is None:
                per_covenant[cov.id] = {
                    "ruin_multiple": None,
                    "report": f"FRAGILE: {reason or 'missing_current'}",
                    "ruin_cause": f"covenant:{cov.id}",
                    "status": Status.RED.value,
                    "fragile_unknown": True,
                }
                statuses.append(Status.RED)
                drivers.append(f"covenant:{cov.id}:unknown")
                if first_breach is None:
                    first_breach = f"covenant:{cov.id}"
                    first_breach_multiple = 0.0
                continue
            if wor is None or wor <= 0:
                per_covenant[cov.id] = {
                    "ruin_multiple": None,
                    "report": "FRAGILE: missing cited worst_on_record on stress_input",
                    "ruin_cause": f"covenant:{cov.id}",
                    "status": Status.RED.value,
                    "fragile_unknown": True,
                }
                statuses.append(Status.RED)
                drivers.append(f"covenant:{cov.id}:missing_wor")
                if first_breach is None:
                    first_breach = f"covenant:{cov.id}"
                    first_breach_multiple = 0.0
                continue

            if headroom <= 0:
                ruin_multiple = 0.0
                report = "already at or past covenant limit"
            else:
                ruin_multiple = float(headroom) / float(wor)
                report = (
                    f"covenant breach at {ruin_multiple:.4f}× "
                    f"worst_on_record (headroom={headroom})"
                )

            st = _status_for_multiple(
                ruin_multiple, thresholds, no_ruin_in_range=False
            )
            per_covenant[cov.id] = {
                "ruin_multiple": ruin_multiple,
                "report": report,
                "ruin_cause": f"covenant:{cov.id}",
                "headroom": headroom,
                "worst_on_record": float(wor),
                "kind": cov.kind.value if hasattr(cov.kind, "value") else cov.kind,
                "metric": cov.metric,
                "limit": cov.limit,
                "current": cov.current,
                "status": st.value,
            }
            statuses.append(st)
            drivers.append(f"covenant:{cov.id}:{ruin_multiple:.3f}x")
            if headline_multiple is None or ruin_multiple < headline_multiple:
                headline_multiple = ruin_multiple
            if first_breach_multiple is None or ruin_multiple < first_breach_multiple:
                first_breach = f"covenant:{cov.id}"
                first_breach_multiple = ruin_multiple

    # If flow-based inputs produced a smaller multiple, that is first_breach.
    if headline_multiple is not None:
        for iid, info in per_input.items():
            rm = info.get("ruin_multiple")
            if rm is None:
                continue
            cause = info.get("ruin_cause") or "survival_floor"
            if first_breach_multiple is None or float(rm) < first_breach_multiple - 1e-15:
                first_breach = str(cause)
                first_breach_multiple = float(rm)
            elif (
                first_breach_multiple is not None
                and abs(float(rm) - first_breach_multiple) <= 1e-15
                and first_breach and first_breach.startswith("covenant:")
            ):
                # Prefer reporting the earlier-evaluated smaller-or-equal flow line
                # only when strictly smaller; ties keep covenant if it was first set.
                pass

    overall = Status.GREEN
    for st in statuses:
        if _RANK[st] > _RANK[overall]:
            overall = st

    if overall == Status.NOT_TESTED and headline_multiple is None and not per_covenant:
        reasons = [
            f"{iid}:{info.get('report')}"
            for iid, info in per_input.items()
            if info.get("status") == Status.NOT_TESTED.value
        ]
        meaning = (
            "NOT TESTED: "
            + ("; ".join(reasons) if reasons else "missing worst_on_record or ruin_line. ")
            + " Distance to ruin needs per-input anchors — not a probability of ruin."
        )
    else:
        meaning = (
            "Per-input / per-covenant distance to ruin in multiples of "
            "worst-on-record. Never averaged; first breach reported. "
            "Structural probe — not a probability of ruin."
        )
        if first_breach:
            meaning = f"First breach={first_breach}. " + meaning

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(headline_multiple) if headline_multiple is not None else 0.0,
        status=overall,
        drivers=drivers,
        inputs={
            "F0": f0,
            "ruin_lines": lines,
            "per_input": per_input,
            "per_covenant": per_covenant,
            "first_breach": first_breach,
            "first_breach_multiple": first_breach_multiple,
            "threshold_version": t.version,
            "red_max_multiple": t.red_max_multiple,
            "amber_max_multiple": t.amber_max_multiple,
            "scan_max_multiple": scan_max,
            "headline_ruin_multiple": headline_multiple,
        },
        meaning=meaning,
        unit="multiple",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description=(
            "Distance to ruin: smallest worst-on-record multiple "
            "that crosses a configured ruin line."
        )
    )
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help="Override survival floor used as a ruin line.",
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
