from metrics.optionality import compute


def test_two_parallel_routes_optionality_two(load_example):
    result = compute(load_example("two_parallel_routes"))
    assert result.value == 2.0
    assert result.status.value == "green"


def test_one_route_optionality_one(load_example):
    result = compute(load_example("one_route"))
    assert result.value == 1.0
    assert result.status.value == "amber"


def test_chain_abc_optionality_one(load_example):
    result = compute(load_example("chain_abc"))
    assert result.value == 1.0


def test_bypass_raises_optionality(load_example):
    result = compute(load_example("chain_abc_with_bypass"))
    assert result.value == 2.0
