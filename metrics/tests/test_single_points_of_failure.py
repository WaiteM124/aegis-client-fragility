import networkx as nx

from metrics.contracts import Status
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


def test_sole_supplier_on_critical_path_is_red():
    """Any cut node marked critical (e.g. sole supplier) is RED on its own."""
    g = nx.DiGraph(client_id="client", name="sole_critical")
    g.add_node("s1", kind="supplier", critical=True)
    g.add_node("client", kind="buyer", critical=False)
    g.add_edge("s1", "client", share=1.0, flow=100, capacity=100, buffer=0)
    result = compute(g)
    assert result.value == 1.0
    assert "s1" in result.drivers
    assert result.status == Status.RED
    assert "s1" in result.inputs.get("critical_spofs", [])


def test_one_cut_node_on_non_critical_path_is_amber():
    """Cut node without critical=true stays AMBER (criticality is explicit)."""
    g = nx.DiGraph(client_id="C", name="noncritical_cut")
    g.add_node("A", kind="supplier", critical=False)
    g.add_node("B", kind="asset", critical=False)
    g.add_node("C", kind="buyer", critical=False)
    g.add_edge("A", "B", share=1.0, flow=100, capacity=100, buffer=0)
    g.add_edge("B", "C", share=1.0, flow=100, capacity=100, buffer=0)
    result = compute(g)
    assert result.value >= 1.0
    assert result.status == Status.AMBER
    assert result.inputs.get("critical_spofs") == []


def test_no_cut_nodes_is_green(load_example):
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == 0.0
    assert result.status == Status.GREEN
    assert result.drivers == []


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


def test_critical_spof_among_noncritical_is_still_red():
    g = nx.DiGraph(client_id="C", name="mixed")
    g.add_node("A", kind="supplier", critical=True)
    g.add_node("B", kind="asset", critical=False)
    g.add_node("C", kind="buyer", critical=False)
    g.add_edge("A", "B", share=1.0, flow=100, capacity=100, buffer=0)
    g.add_edge("B", "C", share=1.0, flow=100, capacity=100, buffer=0)
    result = compute(g)
    assert "A" in result.inputs["critical_spofs"]
    assert result.status == Status.RED
