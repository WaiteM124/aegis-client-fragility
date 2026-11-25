"""Distance-to-ruin known-answer tests."""

from __future__ import annotations

import pytest
from networkx import DiGraph

from metrics.contracts import (
    DependencyGraphSpec,
    EdgeSpec,
    GraphInputSpec,
    NodeKind,
    NodeSpec,
    RuinLineSpec,
    Status,
)
from metrics.distance_to_ruin import compute
from metrics.graph_loader import spec_to_networkx
from metrics.thresholds import DistanceToRuinThresholds, Thresholds


def _linear_company(
    *,
    worst_on_record: float = 0.4,
    survival_floor: float = 0.5,
    include_ruin_line: bool = True,
    include_wor: bool = True,
) -> DiGraph:
    """Linear stress response: remaining = F0 * (1 - intensity).

    Ruin when remaining < floor * F0 ⟺ intensity > 1 - floor.
    At floor=0.5, ruin for intensity > 0.5.
    With worst_on_record=W, ruin multiple = 0.5 / W.
    For W=0.4 → multiple = 1.25 (strictly above 0.5 at first crossing).
    """
    inputs = []
    if include_wor:
        inputs.append(
            GraphInputSpec(
                id="supply_shock",
                worst_on_record=worst_on_record,
                lower_bound=0.0,
                upper_bound=1.0,
            )
        )
    else:
        inputs.append(
            GraphInputSpec(
                id="supply_shock",
                worst_on_record=None,
                lower_bound=0.0,
                upper_bound=1.0,
            )
        )
    ruin_line = (
        RuinLineSpec(survival_floor=survival_floor) if include_ruin_line else None
    )
    spec = DependencyGraphSpec(
        name="linear_dtr",
        nodes=[
            NodeSpec(id="s1", kind=NodeKind.SUPPLIER),
            NodeSpec(id="client", kind=NodeKind.BUYER),
        ],
        edges=[
            EdgeSpec(
                source="s1",
                target="client",
                share=1.0,
                flow=100,
                capacity=100,
                buffer=0,
                stress_response="linear",
            )
        ],
        survival_floor=survival_floor,
        inputs=inputs,
        ruin_line=ruin_line,
    )
    return spec_to_networkx(spec)


def test_known_break_at_1_25x():
    """Linear graph, floor 0.5, W=0.4 → ruin when intensity > 0.5 → ~1.25× record."""
    g = _linear_company(worst_on_record=0.4, survival_floor=0.5)
    result = compute(g)
    assert result.status != Status.NOT_TESTED
    per = result.inputs["per_input"]["supply_shock"]
    assert per["ruin_multiple"] == pytest.approx(1.25, abs=0.05)
    assert per["ruin_cause"] in {"survival_floor", "covenant_breach_flow_fraction"}


def test_known_break_near_1_3x():
    """Tune W so break ≈ 1.3×: need (1 - floor) / W = 1.3 → W = 0.5/1.3 ≈ 0.3846."""
    w = 0.5 / 1.3
    g = _linear_company(worst_on_record=w, survival_floor=0.5)
    result = compute(g)
    per = result.inputs["per_input"]["supply_shock"]
    assert per["ruin_multiple"] == pytest.approx(1.3, abs=0.05)


def test_no_break_in_scan_range_reported():
    """High floor tolerance + small record move → no ruin within scan."""
    # floor=0.05 → ruin only when intensity > 0.95; W=0.1 → 5× = 0.5 < 0.95
    g = _linear_company(worst_on_record=0.1, survival_floor=0.05)
    # Cap scan at 5× so 0.5 intensity never crosses
    thresholds = Thresholds(
        distance_to_ruin=DistanceToRuinThresholds(scan_max_multiple=5.0)
    )
    result = compute(g, thresholds=thresholds)
    per = result.inputs["per_input"]["supply_shock"]
    assert per["ruin_multiple"] is None
    assert "no ruin within" in per["report"].lower()
    assert result.status == Status.GREEN


def test_missing_worst_on_record_not_tested():
    g = _linear_company(include_wor=False)
    result = compute(g)
    assert result.status == Status.NOT_TESTED
    assert "worst_on_record" in result.meaning.lower() or "missing" in result.meaning.lower()


def test_missing_ruin_line_and_floor_not_tested():
    g = _linear_company(include_ruin_line=False, survival_floor=0.5)
    # Clear both graph survival_floor and ruin_line so nothing remains
    g.graph.pop("survival_floor", None)
    g.graph.pop("ruin_line", None)
    result = compute(g)
    # Default thresholds still supply a floor — force absence via thresholds
    thresholds = Thresholds(
        distance_to_ruin=DistanceToRuinThresholds(),
    )
    # Override: pass require_explicit_ruin_line behaviour — metric should use
    # graph ruin_line OR survival_floor OR thresholds. To get NOT_TESTED for
    # missing ruin line, clear threshold floor by custom compute path.
    # Spec: missing ruin_line OR worst_on_record → NOT_TESTED.
    # With no ruin_line on graph and we treat thresholds default as present,
    # require explicit ruin_line on graph for DTR.
    result = compute(g, thresholds=thresholds, require_explicit_ruin_line=True)
    assert result.status == Status.NOT_TESTED


def test_input_without_break_does_not_hide_breaking_input():
    """Two inputs: one never ruins in range; the other breaks at 1× → overall RED."""
    spec = DependencyGraphSpec(
        name="two_inputs",
        nodes=[
            NodeSpec(id="s1", kind=NodeKind.SUPPLIER),
            NodeSpec(id="client", kind=NodeKind.BUYER),
        ],
        edges=[
            EdgeSpec(
                source="s1",
                target="client",
                share=1.0,
                flow=100,
                capacity=100,
                buffer=0,
                stress_response="linear",
            )
        ],
        survival_floor=0.5,
        ruin_line=RuinLineSpec(survival_floor=0.5),
        inputs=[
            GraphInputSpec(
                id="tiny_move",
                worst_on_record=0.05,  # 5× = 0.25 < 0.5 → no ruin in scan
                lower_bound=0.0,
                upper_bound=1.0,
            ),
            GraphInputSpec(
                id="big_move",
                # Ruin when intensity > 0.5 → multiple > 0.5/0.6 ≈ 0.833 ≤ 1× → RED
                worst_on_record=0.6,
                lower_bound=0.0,
                upper_bound=1.0,
            ),
        ],
    )
    g = spec_to_networkx(spec)
    result = compute(g)
    per = result.inputs["per_input"]
    assert per["tiny_move"]["ruin_multiple"] is None
    assert per["big_move"]["ruin_multiple"] is not None
    assert per["big_move"]["ruin_multiple"] == pytest.approx(0.5 / 0.6, abs=0.05)
    # Worst input drives status: break at ~0.83× ≤ 1× → RED
    assert result.status == Status.RED


def test_status_cutoffs_from_config_not_hardcoded():
    g = _linear_company(worst_on_record=0.4, survival_floor=0.5)  # ~1.25×
    # With red_max=1.0, amber_max=2.0 → 1.25 is AMBER
    result = compute(g)
    assert result.status == Status.AMBER
    # Tighten amber so 1.25 is still red-equivalent by lowering red_max
    tight = Thresholds(
        distance_to_ruin=DistanceToRuinThresholds(
            red_max_multiple=1.3, amber_max_multiple=2.0
        )
    )
    result2 = compute(g, thresholds=tight)
    assert result2.status == Status.RED
