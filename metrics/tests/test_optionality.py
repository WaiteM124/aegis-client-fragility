"""Known-answer tests for node-disjoint optionality (Menger / max-flow)."""

from metrics.optionality import VERSION, compute, count_optionality


def test_hidden_shared_subtier_is_one_route_not_green(load_example):
    """Both apparent corridors share supplier 'subtier' — not independent."""
    graph = load_example("hidden_shared_subtier")
    o, paths = count_optionality(graph)
    assert o == 1
    assert len(paths) == 1
    result = compute(graph)
    assert result.value == 1.0
    assert result.status.value != "green"
    assert result.status.value == "amber"
    assert any("subtier" in d for d in result.drivers)
    assert VERSION != "1.0.0"


def test_two_parallel_routes_shared_source_is_one(load_example):
    """Two routes from the same supplier are not node-disjoint (source shared)."""
    result = compute(load_example("two_parallel_routes"))
    assert result.value == 1.0
    assert result.status.value == "amber"
    assert any("s1" in d for d in result.drivers)


def test_truly_independent_corridors_remain_two(load_example):
    """Independent supplier→route→buyer corridors stay at O = 2 (control shape)."""
    from metrics.contracts import DependencyGraphSpec, NodeKind
    from metrics.graph_loader import spec_to_networkx

    spec = DependencyGraphSpec.model_validate(
        {
            "name": "truly_independent",
            "nodes": [
                {"id": "s1", "kind": NodeKind.SUPPLIER},
                {"id": "s2", "kind": NodeKind.SUPPLIER},
                {"id": "route_n", "kind": NodeKind.ROUTE},
                {"id": "route_s", "kind": NodeKind.ROUTE},
                {"id": "client", "kind": NodeKind.BUYER},
            ],
            "edges": [
                {"source": "s1", "target": "route_n", "share": 0.5, "flow": 50, "capacity": 80},
                {"source": "route_n", "target": "client", "share": 0.5, "flow": 50, "capacity": 80},
                {"source": "s2", "target": "route_s", "share": 0.5, "flow": 50, "capacity": 80},
                {"source": "route_s", "target": "client", "share": 0.5, "flow": 50, "capacity": 80},
            ],
        }
    )
    result = compute(spec_to_networkx(spec))
    assert result.value == 2.0
    assert result.status.value == "green"


def test_one_route_optionality_one(load_example):
    result = compute(load_example("one_route"))
    assert result.value == 1.0
    assert result.status.value == "amber"


def test_chain_abc_optionality_one(load_example):
    result = compute(load_example("chain_abc"))
    assert result.value == 1.0


def test_bypass_same_source_does_not_inflate_optionality(load_example):
    """Bypass around B still shares supplier A — still one node-disjoint corridor."""
    result = compute(load_example("chain_abc_with_bypass"))
    assert result.value == 1.0
    assert result.status.value == "amber"


def test_four_equal_suppliers_optionality_four(load_example):
    result = compute(load_example("four_equal_suppliers"))
    assert result.value == 4.0
    assert result.status.value == "green"


def test_shared_hub_collapses_to_one(load_example):
    """Two suppliers through one hub → one independent corridor; driver names hub."""
    from metrics.contracts import DependencyGraphSpec, NodeKind
    from metrics.graph_loader import spec_to_networkx

    spec = DependencyGraphSpec.model_validate(
        {
            "name": "shared_hub",
            "nodes": [
                {"id": "s1", "kind": NodeKind.SUPPLIER},
                {"id": "s2", "kind": NodeKind.SUPPLIER},
                {"id": "hub", "kind": NodeKind.ASSET},
                {"id": "client", "kind": NodeKind.BUYER},
            ],
            "edges": [
                {"source": "s1", "target": "hub", "share": 0.5, "flow": 50, "capacity": 60},
                {"source": "s2", "target": "hub", "share": 0.5, "flow": 50, "capacity": 60},
                {"source": "hub", "target": "client", "share": 1.0, "flow": 100, "capacity": 110},
            ],
        }
    )
    result = compute(spec_to_networkx(spec))
    assert result.value == 1.0
    assert any("hub" in d for d in result.drivers)
