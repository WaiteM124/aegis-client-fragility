from metrics.cascade_depth import compute


def test_chain_abc_depth_is_two(load_example):
    result = compute(load_example("chain_abc"))
    assert result.value == 2.0
    assert "A" in result.drivers


def test_direct_suppliers_depth_is_one(load_example):
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == 1.0


def test_hidden_subtier_depth_is_two(load_example):
    result = compute(load_example("hidden_shared_subtier"))
    assert result.value == 2.0
