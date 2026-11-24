import networkx as nx

from metrics.contracts import Scenario
from metrics.ruin import compute, resolve_survival_floor
from metrics.thresholds import THRESHOLDS


def test_default_survival_floor_is_half():
    assert THRESHOLDS.ruin.survival_floor == 0.5


def test_linear_graph_exact_half_remaining_is_not_ruin(load_example):
    # Default ladder max δ=0.5 leaves F=0.5·F0 on a linear graph.
    # Strict <: remaining equal to the floor is not ruin.
    result = compute(load_example("single_supplier"))
    assert result.inputs["survival_floor"] == 0.5
    assert result.inputs["remaining"]["0.5"] == 50.0
    assert result.value == 0.0
    assert result.status.value == "green"


def test_sixty_percent_loss_triggers_ruin_at_floor_half(load_example):
    # Custom ladder: δ=0.6 → 60% loss → remaining 40% < 0.5 → ruin
    result = compute(load_example("single_supplier"), ladder=(0.10, 0.20, 0.60))
    assert result.value == 1.0
    assert result.status.value == "red"
    assert any("0.6" in d for d in result.drivers)


def test_forty_percent_loss_does_not_trigger_at_floor_half(load_example):
    # Ladder that never goes past 40% loss → remaining ≥ 60% ≥ floor
    result = compute(load_example("single_supplier"), ladder=(0.10, 0.20, 0.40))
    assert result.inputs["remaining"]["0.4"] == 60.0
    assert result.value == 0.0
    assert result.status.value == "green"


def test_cliff_graph_is_ruin(load_example):
    result = compute(load_example("ruin_cliff"))
    assert result.value == 1.0
    assert result.status.value == "red"
    assert any("0.5" in d for d in result.drivers)


def test_scenario_survival_floor_override(load_example):
    scenario = Scenario(survival_floor=0.55)
    result = compute(load_example("single_supplier"), scenario)
    # 50% stress leaves 50% flow, which is < 0.55 → ruin
    assert result.value == 1.0
    assert result.status.value == "red"


def test_graph_yaml_survival_floor_override(load_example):
    # low_survival_floor.yaml sets survival_floor: 0.3 so a 50% stress is OK
    g = load_example("low_survival_floor")
    assert resolve_survival_floor(g) == 0.3
    result = compute(g)
    assert result.inputs["survival_floor"] == 0.3
    assert result.value == 0.0
    assert result.status.value == "green"


def test_graph_yaml_high_floor_triggers_at_fifty(load_example):
    g = load_example("high_survival_floor")
    assert resolve_survival_floor(g) == 0.6
    result = compute(g)
    # remaining at δ=0.5 is 50% < 0.6 → ruin
    assert result.value == 1.0
    assert result.status.value == "red"


def test_scenario_overrides_graph_yaml(load_example):
    g = load_example("high_survival_floor")
    # Graph says 0.6 (would ruin); scenario lowers to 0.4 (survives at 50%)
    result = compute(g, Scenario(survival_floor=0.4))
    assert result.inputs["survival_floor"] == 0.4
    assert result.value == 0.0


def test_resolve_priority_scenario_over_graph_over_default():
    g = nx.DiGraph(client_id="c", survival_floor=0.3)
    g.add_node("s", kind="supplier")
    g.add_node("c", kind="buyer")
    g.add_edge("s", "c", share=1.0, flow=100, capacity=100, buffer=0)
    assert resolve_survival_floor(g) == 0.3
    assert resolve_survival_floor(g, Scenario(survival_floor=0.8)) == 0.8
    g2 = nx.DiGraph(client_id="c")
    assert resolve_survival_floor(g2) == 0.5
