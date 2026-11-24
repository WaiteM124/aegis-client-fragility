import networkx as nx
import pytest

from metrics.monoculture import compute


def test_single_supplier_is_full_monoculture(load_example):
    result = compute(load_example("single_supplier"))
    assert result.value == pytest.approx(1.0)
    assert result.status.value == "red"


def test_four_equal_diversified_attributes_lower(load_example):
    # four_equal has distinct regions → region monoculture = 0.25
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == pytest.approx(0.5)  # type=semiconductor on s1+s2
    assert "type:semiconductor" in result.drivers


def test_explicit_region_monoculture():
    g = nx.DiGraph(client_id="client")
    g.add_node("s1", kind="supplier", region="asia", type="a", technology="t")
    g.add_node("s2", kind="supplier", region="asia", type="b", technology="u")
    g.add_node("client", kind="buyer")
    g.add_edge("s1", "client", share=0.6, flow=60, capacity=60, buffer=0)
    g.add_edge("s2", "client", share=0.4, flow=40, capacity=40, buffer=0)
    result = compute(g)
    assert result.value == pytest.approx(1.0)
    assert "region:asia" in result.drivers
