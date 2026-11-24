from metrics.contracts import Status
from metrics.run_all import format_grouped, run_all, worst_status


def test_run_all_returns_four_groups(load_example):
    results = run_all(load_example("four_equal_suppliers"))
    assert set(results) == {"Concentration", "Contagion", "Convexity", "Optionality"}
    assert all(len(v) == 2 for v in results.values())


def test_no_blended_score_in_output(load_example):
    text = format_grouped(run_all(load_example("four_equal_suppliers")))
    assert "blended" not in text.lower() or "No blended" in text
    assert "weighted" not in text.lower()
    assert "Concentration" in text
    assert "Contagion" in text
    assert "Convexity" in text
    assert "Optionality" in text


def test_ruin_forces_convexity_group_red(load_example):
    results = run_all(load_example("ruin_cliff"))
    group_status = worst_status(results["Convexity"], ruin_forces_red=True)
    assert group_status == Status.RED
    ruin_result = next(r for r in results["Convexity"] if r.metric == "ruin")
    assert ruin_result.status == Status.RED


def test_hidden_subtier_flags_spof(load_example):
    results = run_all(load_example("hidden_shared_subtier"))
    spof = next(r for r in results["Contagion"] if r.metric == "single_points_of_failure")
    assert "subtier" in spof.drivers
