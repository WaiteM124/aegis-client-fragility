from metrics.single_points_of_failure import compute, find_spofs


def test_chain_abc_b_is_spof(load_example):
    g = load_example("chain_abc")
    spofs = find_spofs(g)
    assert "B" in spofs
    # A is also a SPOF (sole supplier); C is the client and excluded
    assert "C" not in spofs
    result = compute(g)
    assert result.value >= 1
    assert "B" in result.drivers


def test_bypass_removes_b_as_spof(load_example):
    g = load_example("chain_abc_with_bypass")
    spofs = find_spofs(g)
    assert "B" not in spofs
    assert "D" not in spofs
    # Sole supplier A remains a SPOF
    assert "A" in spofs


def test_four_equal_no_intermediate_spof(load_example):
    spofs = find_spofs(load_example("four_equal_suppliers"))
    # Direct supplier→client edges: removing one supplier does not disconnect
    assert spofs == []
