from metrics.graph_loader import client_id, load_graph, supplier_shares


def test_load_four_equal(examples_dir):
    g = load_graph(examples_dir / "four_equal_suppliers.yaml")
    assert client_id(g) == "client"
    assert g.number_of_nodes() == 5
    assert g.number_of_edges() == 4
    shares = supplier_shares(g)
    assert shares == {"s1": 0.25, "s2": 0.25, "s3": 0.25, "s4": 0.25}


def test_stress_response_preserved(examples_dir):
    g = load_graph(examples_dir / "ruin_cliff.yaml")
    assert g["s1"]["client"]["stress_response"] == "cliff"
