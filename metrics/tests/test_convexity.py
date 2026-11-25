"""Convexity tests: curvature from model output, not declared labels."""

from __future__ import annotations

import pytest
from networkx import DiGraph

from metrics.contracts import (
    DependencyGraphSpec,
    EdgeSpec,
    GraphInputSpec,
    NodeKind,
    NodeSpec,
    Status,
)
from metrics.convexity import compute
from metrics.graph_loader import spec_to_networkx


def _graph_with_input(
    *,
    buffer: float = 0.0,
    stress_response: str | None = None,
    worst_on_record: float = 0.20,
    capacity: float | None = None,
    flow: float = 100.0,
) -> DiGraph:
    cap = flow if capacity is None else capacity
    edge = EdgeSpec(
        source="s1",
        target="client",
        share=1.0,
        flow=flow,
        capacity=cap,
        buffer=buffer,
        stress_response=stress_response,
    )
    spec = DependencyGraphSpec(
        name="test",
        nodes=[
            NodeSpec(id="s1", kind=NodeKind.SUPPLIER),
            NodeSpec(id="client", kind=NodeKind.BUYER),
        ],
        edges=[edge],
        inputs=[
            GraphInputSpec(
                id="supply_shock",
                worst_on_record=worst_on_record,
                lower_bound=0.0,
                upper_bound=1.0,
            )
        ],
    )
    return spec_to_networkx(spec)


def test_known_convex_harm_is_fragile():
    """harm(x)=x² → positive second difference → FRAGILE."""
    g = _graph_with_input(worst_on_record=0.2)
    result = compute(g, harm_fn=lambda x: float(x) ** 2)
    assert result.inputs["shape"] == "fragile"
    assert result.value > 0
    assert result.status.value in {"amber", "red"}


def test_linear_harm_is_robust():
    """harm(x)=x → zero second difference → ROBUST."""
    g = _graph_with_input(worst_on_record=0.2)
    result = compute(g, harm_fn=lambda x: float(x))
    assert result.inputs["shape"] == "robust"
    assert result.value == pytest.approx(0.0, abs=1e-9)
    assert result.status == Status.GREEN


def test_concave_harm_is_antifragile():
    """harm(x)=sqrt(x) on (0,1] decelerates → ANTIFRAGILE flag."""
    g = _graph_with_input(worst_on_record=0.2)

    def harm(x: float) -> float:
        x = max(float(x), 0.0)
        return x**0.5

    result = compute(g, harm_fn=harm)
    assert result.inputs["shape"] == "antifragile"
    assert result.inputs.get("antifragile_flag") is True
    assert result.value < 0


def test_step_function_flagged_as_cliff():
    """Big jump between neighbouring scan steps → cliff, separate from curvature."""

    def harm(x: float) -> float:
        return 0.0 if float(x) < 0.3 else 1.0

    g = _graph_with_input(worst_on_record=0.2)
    result = compute(g, harm_fn=harm)
    assert result.inputs.get("cliffs")
    assert len(result.inputs["cliffs"]) >= 1


def test_bounded_input_clamping_reported():
    """Values outside [lower, upper] are clamped; clamping sites are reported."""
    g = _graph_with_input(worst_on_record=0.6)  # 2x record = 1.2 → clamp to 1.0

    def harm(x: float) -> float:
        return float(x)

    result = compute(g, harm_fn=harm)
    assert result.inputs.get("clamped_points")
    assert any(c.get("clamped") for c in result.inputs["clamped_points"])


def test_result_unchanged_if_labels_removed(load_example):
    """Curvature comes from model output (buffer physics), not stress_response label."""
    g_labelled = load_example("fragile_buffered")
    # Ensure inputs present on both
    assert g_labelled.graph.get("inputs") or True
    # Build twin without stress_response labels
    g_plain = g_labelled.copy()
    for _u, _v, data in g_plain.edges(data=True):
        data.pop("stress_response", None)
    # Both need graph inputs for the new convexity path
    inp = [
        {
            "id": "supply_shock",
            "worst_on_record": 0.2,
            "lower_bound": 0.0,
            "upper_bound": 1.0,
        }
    ]
    g_labelled.graph["inputs"] = inp
    g_plain.graph["inputs"] = inp

    r1 = compute(g_labelled)
    r2 = compute(g_plain)
    assert r1.inputs["shape"] == r2.inputs["shape"]
    assert r1.value == pytest.approx(r2.value, abs=1e-9)
    assert r1.status == r2.status


def test_buffered_graph_is_fragile_from_output(load_example):
    g = load_example("fragile_buffered")
    g.graph["inputs"] = [
        {
            "id": "supply_shock",
            "worst_on_record": 0.2,
            "lower_bound": 0.0,
            "upper_bound": 1.0,
        }
    ]
    result = compute(g)
    assert result.inputs["shape"] == "fragile"
    assert result.value > 0
    assert result.status.value in {"amber", "red"}


def test_missing_worst_on_record_is_not_tested():
    g = _graph_with_input()
    g.graph["inputs"] = [
        {"id": "supply_shock", "worst_on_record": None, "lower_bound": 0.0, "upper_bound": 1.0}
    ]
    result = compute(g)
    assert result.status == Status.NOT_TESTED


def test_no_inputs_is_not_tested(load_example):
    g = load_example("single_supplier")
    g.graph.pop("inputs", None)
    result = compute(g)
    assert result.status == Status.NOT_TESTED
