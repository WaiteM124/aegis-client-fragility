from metrics.contracts import Scenario, Status
from metrics.run_all import format_grouped, run_all, worst_status


def test_run_all_returns_four_groups(load_example):
    results = run_all(load_example("four_equal_suppliers"))
    assert set(results) == {"Concentration", "Contagion", "Convexity", "Optionality"}
    # Convexity group now has convexity, ruin, distance_to_ruin
    assert len(results["Concentration"]) == 2
    assert len(results["Contagion"]) == 2
    assert len(results["Convexity"]) == 3
    assert len(results["Optionality"]) == 2


def test_no_blended_score_in_output(load_example):
    text = format_grouped(run_all(load_example("four_equal_suppliers")))
    assert "blended" not in text.lower() or "No blended" in text
    assert "weighted" not in text.lower()
    assert "Concentration" in text
    assert "Contagion" in text
    assert "Convexity" in text
    assert "Optionality" in text


def test_ruin_forces_convexity_group_red(load_example):
    results = run_all(
        load_example("ruin_cliff"),
        Scenario(run_stress_ladder=True),
    )
    group_status = worst_status(results["Convexity"], ruin_forces_red=True)
    assert group_status == Status.RED
    ruin_result = next(r for r in results["Convexity"] if r.metric == "ruin")
    assert ruin_result.status == Status.RED


def test_run_all_never_treats_not_tested_as_green(load_example):
    """Without an explicit probe, ruin is NOT_TESTED and must not pass as green."""
    results = run_all(load_example("four_equal_suppliers"))
    ruin_result = next(r for r in results["Convexity"] if r.metric == "ruin")
    assert ruin_result.status == Status.NOT_TESTED
    group_status = worst_status(results["Convexity"], ruin_forces_red=True)
    assert group_status != Status.GREEN
    assert group_status == Status.NOT_TESTED or group_status in {
        Status.AMBER,
        Status.RED,
        Status.NOT_TESTED,
    }
    text = format_grouped(results)
    assert "NOT_TESTED" in text


def test_worst_status_not_tested_outranks_green():
    from metrics.contracts import MetricResult

    green = MetricResult(
        metric="convexity", version="1", value=0.0, status=Status.GREEN
    )
    nt = MetricResult(
        metric="ruin", version="1", value=0.0, status=Status.NOT_TESTED
    )
    assert worst_status([green, nt]) == Status.NOT_TESTED


def test_hidden_subtier_flags_spof(load_example):
    results = run_all(load_example("hidden_shared_subtier"))
    spof = next(r for r in results["Contagion"] if r.metric == "single_points_of_failure")
    assert "subtier" in spof.drivers
