"""ChillCo example: chilled ready-meals supply-side fragility (made-up EXAMPLE DATA)."""

from pathlib import Path

from metrics.contracts import Scenario, Status
from metrics.graph_loader import load_graph
from metrics.run_all import run_all

CHILLCO_GRAPH = (
    Path(__file__).resolve().parents[2] / "clients" / "chillco" / "model" / "chillco.yaml"
)


def test_chillco_stress_ladder_findings():
    """run_all with stress ladder: haulier SPOF red, optionality not green, ruin tested."""
    results = run_all(
        load_graph(CHILLCO_GRAPH),
        Scenario(run_stress_ladder=True),
    )

    spof = next(r for r in results["Contagion"] if r.metric == "single_points_of_failure")
    assert spof.status == Status.RED
    assert "haulier_x" in spof.drivers

    opt = next(r for r in results["Optionality"] if r.metric == "optionality")
    assert opt.status != Status.GREEN
    assert any("haulier_x" in d for d in opt.drivers)

    ruin_result = next(r for r in results["Convexity"] if r.metric == "ruin")
    assert ruin_result.status != Status.NOT_TESTED
