import pytest

from metrics.slack import compute


def test_single_supplier_zero_buffer_zero_spare(load_example):
    result = compute(load_example("single_supplier"))
    assert result.value == pytest.approx(0.0)
    assert result.status.value == "red"


def test_four_equal_has_positive_slack(load_example):
    # spare=15, buffer=5, flow=25 → slack = 20/25 = 0.8
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == pytest.approx(0.8)
    assert result.status.value == "green"


def test_tight_capacity_is_red(load_example):
    result = compute(load_example("chain_abc"))
    assert result.value == pytest.approx(0.0)
    assert result.status.value == "red"
