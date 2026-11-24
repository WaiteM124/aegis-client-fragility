import pytest

from metrics.convexity import compute


def test_linear_graph_is_robust(load_example):
    # capacity=flow, buffer=0 → buffered profile reduces to linear
    result = compute(load_example("single_supplier"))
    assert result.inputs["shape"] == "robust"
    assert result.value == pytest.approx(0.0)
    assert result.status.value == "green"


def test_buffered_graph_is_fragile(load_example):
    result = compute(load_example("fragile_buffered"))
    assert result.inputs["shape"] == "fragile"
    assert result.value > 0
    assert result.status.value in {"amber", "red"}


def test_decelerating_graph_is_antifragile(load_example):
    result = compute(load_example("antifragile_decelerating"))
    assert result.inputs["shape"] == "antifragile"
    assert result.value < 0
    assert result.status.value == "green"


def test_ladder_losses_present(load_example):
    result = compute(load_example("single_supplier"))
    losses = result.inputs["losses"]
    assert set(losses) == {"0.1", "0.2", "0.5"}
    assert losses["0.1"] == pytest.approx(10.0)
    assert losses["0.2"] == pytest.approx(20.0)
    assert losses["0.5"] == pytest.approx(50.0)
