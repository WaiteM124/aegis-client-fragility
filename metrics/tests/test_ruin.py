from metrics.contracts import Scenario
from metrics.ruin import compute


def test_linear_graph_no_ruin_at_default_floor(load_example):
    result = compute(load_example("single_supplier"))
    assert result.value == 0.0
    assert result.status.value == "green"


def test_cliff_graph_is_ruin(load_example):
    result = compute(load_example("ruin_cliff"))
    assert result.value == 1.0
    assert result.status.value == "red"
    assert any("0.5" in d for d in result.drivers)


def test_raised_survival_floor_flags_ruin(load_example):
    scenario = Scenario(survival_floor=0.55)
    result = compute(load_example("single_supplier"), scenario)
    # 50% stress leaves 50% flow, which is below 0.55 → ruin
    assert result.value == 1.0
    assert result.status.value == "red"
