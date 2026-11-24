import pytest

from metrics.hhi import compute


def test_single_supplier_hhi_is_one(load_example):
    result = compute(load_example("single_supplier"))
    assert result.value == pytest.approx(1.0)
    assert result.status.value == "red"


def test_four_equal_suppliers_hhi_is_quarter(load_example):
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == pytest.approx(0.25)
    assert result.status.value == "green"
