"""Tests for optional financial-side model sections (ADR-019).

Spec-first: schema validation, covenant-before-floor ruin, runway,
customer HHI/SPOF, fixed-price convexity, unknowns flagged fragile.
Old supply-only graphs must still load and keep identical group status.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from metrics.contracts import (
    DependencyGraphSpec,
    Scenario,
    Status,
)
from metrics.convexity import compute as compute_convexity
from metrics.customer_hhi import compute as compute_customer_hhi
from metrics.customer_spof import compute as compute_customer_spof
from metrics.distance_to_ruin import compute as compute_distance_to_ruin
from metrics.energy_margin import compute as compute_energy_margin
from metrics.graph_loader import load_graph, load_graph_spec, spec_to_networkx
from metrics.hhi import compute as compute_hhi
from metrics.ruin import compute as compute_ruin
from metrics.run_all import run_all, worst_status
from metrics.runway import compute as compute_runway

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CLIENTS = Path(__file__).resolve().parents[2] / "clients"
SCHEMAS = CLIENTS / "schemas"
REPO = Path(__file__).resolve().parents[2]


def _base_nodes_edges():
    return {
        "nodes": [
            {"id": "s1", "kind": "supplier", "type": "commodity", "critical": False},
            {"id": "client", "kind": "buyer", "critical": False},
        ],
        "edges": [
            {
                "source": "s1",
                "target": "client",
                "share": 1.0,
                "flow": 100,
                "capacity": 100,
                "buffer": 0,
                "stress_response": "linear",
            }
        ],
    }


def _graph(**extra) -> DependencyGraphSpec:
    data = {"name": "test", **_base_nodes_edges(), **extra}
    return DependencyGraphSpec.model_validate(data)


# ---------------------------------------------------------------------------
# Schema / backward compatibility
# ---------------------------------------------------------------------------


def test_old_example_graphs_still_validate(examples_dir):
    for path in sorted(examples_dir.glob("*.yaml")):
        spec = load_graph_spec(path)
        assert spec.name
        assert spec.liquidity is None
        assert spec.customers == []
        assert spec.covenants == []


def test_old_eval_cases_still_validate():
    cases_dir = REPO / "evals" / "cases"
    for path in sorted(cases_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        DependencyGraphSpec.model_validate(raw["graph"])


def test_supply_only_group_status_unchanged_when_financial_metrics_absent(load_example):
    """optional_section_absent metrics must not change Concentration group."""
    from metrics.monoculture import compute as compute_monoculture

    g = load_example("four_equal_suppliers")
    results = run_all(g)
    # New metrics present but section-absent
    cust = next(r for r in results["Concentration"] if r.metric == "customer_hhi")
    assert cust.status == Status.NOT_TESTED
    assert cust.inputs.get("optional_section_absent") is True
    # Group matches supply-only members (customer_* excluded from roll-up)
    supply_only = [compute_hhi(g), compute_monoculture(g)]
    assert worst_status(results["Concentration"]) == worst_status(supply_only)


def test_dependency_graph_json_schema_accepts_old_and_new():
    schema_path = SCHEMAS / "dependency_graph.v1.json"
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    import jsonschema

    old = yaml.safe_load(
        (EXAMPLES / "four_equal_suppliers.yaml").read_text(encoding="utf-8")
    )
    jsonschema.validate(old, schema, format_checker=jsonschema.FormatChecker())

    new = _graph(
        liquidity={
            "cash_on_hand": 10.0,
            "fixed_monthly_outflows": 2.0,
            "committed_facilities": [],
            "source": {"label": "EXAMPLE DATA", "as_of": "2020-01-01"},
        },
        customers=[
            {
                "id": "big",
                "revenue_share": 0.8,
                "public_sector": False,
                "critical": True,
            }
        ],
    ).model_dump(mode="json")
    jsonschema.validate(new, schema, format_checker=jsonschema.FormatChecker())


# ---------------------------------------------------------------------------
# Liquidity / runway
# ---------------------------------------------------------------------------


def test_runway_months_basic():
    g = spec_to_networkx(
        _graph(
            liquidity={
                "cash_on_hand": 12.0,
                "fixed_monthly_outflows": 3.0,
                "committed_facilities": [
                    {"id": "rcf", "limit": 6.0, "drawn": 0.0},
                ],
                "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
            }
        )
    )
    # available = 12 + 6 = 18; months = 18/3 = 6 → amber boundary (<6 amber, so 6 green)
    result = compute_runway(g, stress_intensity=0.0)
    assert result.value == pytest.approx(6.0)
    assert result.status == Status.GREEN


def test_runway_under_stress():
    g = spec_to_networkx(
        _graph(
            liquidity={
                "cash_on_hand": 12.0,
                "fixed_monthly_outflows": 3.0,
                "committed_facilities": [],
                "stress_input_id": "liq_shock",
                "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
            },
            inputs=[
                {
                    "id": "liq_shock",
                    "worst_on_record": 0.5,
                    "source": {"label": "EXAMPLE", "as_of": "2019-01-01"},
                }
            ],
        )
    )
    # δ=0.5 → available 6 / 3 = 2 months → red
    result = compute_runway(g)
    assert result.value == pytest.approx(2.0)
    assert result.status == Status.RED


def test_runway_unknown_cash_flagged_fragile():
    g = spec_to_networkx(
        _graph(
            liquidity={
                "cash_on_hand": None,
                "fixed_monthly_outflows": 3.0,
                "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
            }
        )
    )
    result = compute_runway(g)
    assert result.status == Status.RED
    assert result.inputs.get("fragile_unknown") is True


def test_runway_absent_section_not_tested():
    g = spec_to_networkx(_graph())
    result = compute_runway(g)
    assert result.status == Status.NOT_TESTED
    assert result.inputs.get("optional_section_absent") is True


# ---------------------------------------------------------------------------
# Covenants as ruin line
# ---------------------------------------------------------------------------


def test_covenant_breaches_before_survival_floor():
    """Covenant headroom/WOR smaller than flow ruin → first_breach is covenant."""
    g = spec_to_networkx(
        _graph(
            ruin_line={"survival_floor": 0.1},  # very low floor — flow hard to ruin
            inputs=[
                {
                    "id": "leverage_shock",
                    # headroom 0.5 / WOR 0.6 ≈ 0.833× → red; at δ=1 stressed=3.6 > 3.5
                    "worst_on_record": 0.6,
                    "lower_bound": 0.0,
                    "upper_bound": 5.0,
                    "source": {"label": "EXAMPLE", "as_of": "2016-01-01"},
                }
            ],
            covenants=[
                {
                    "id": "net_debt_ebitda",
                    "kind": "max",
                    "metric": "net_debt_ebitda",
                    "limit": 3.5,
                    "current": 3.0,
                    "stress_input_id": "leverage_shock",
                    "source": {"label": "EXAMPLE", "as_of": "2016-12-31"},
                }
            ],
        )
    )
    dtr = compute_distance_to_ruin(g)
    assert dtr.inputs.get("first_breach") == "covenant:net_debt_ebitda"
    assert dtr.value == pytest.approx(0.5 / 0.6)
    assert dtr.status == Status.RED

    ruin = compute_ruin(g, Scenario(run_stress_ladder=True, stress_ladder=[0.5, 1.0]))
    assert ruin.status == Status.RED
    assert ruin.inputs.get("first_breach", "").startswith("covenant:")


def test_unknown_covenant_current_flagged_fragile():
    g = spec_to_networkx(
        _graph(
            ruin_line={"survival_floor": 0.5},
            inputs=[
                {
                    "id": "lev",
                    "worst_on_record": 0.2,
                    "source": {"label": "EXAMPLE", "as_of": "2016-01-01"},
                }
            ],
            covenants=[
                {
                    "id": "interest_cover",
                    "kind": "min",
                    "metric": "interest_cover",
                    "limit": 2.0,
                    "current": None,
                    "stress_input_id": "lev",
                    "source": {"label": "EXAMPLE", "as_of": "2016-12-31"},
                }
            ],
        )
    )
    dtr = compute_distance_to_ruin(g)
    assert dtr.status == Status.RED
    assert dtr.inputs["per_covenant"]["interest_cover"].get("fragile_unknown") is True


# ---------------------------------------------------------------------------
# Customer concentration / SPOF
# ---------------------------------------------------------------------------


def test_customer_hhi_dominant():
    g = spec_to_networkx(
        _graph(
            customers=[
                {"id": "a", "revenue_share": 0.9, "critical": True},
                {"id": "b", "revenue_share": 0.1, "critical": False},
            ]
        )
    )
    result = compute_customer_hhi(g)
    assert result.value == pytest.approx(0.9**2 + 0.1**2)
    assert result.status == Status.RED
    assert result.inputs["side"] == "customers"
    # Supplier HHI remains separate
    assert compute_hhi(g).value == pytest.approx(1.0)


def test_customer_spof_single_dominant_red():
    g = spec_to_networkx(
        _graph(
            customers=[
                {
                    "id": "mega",
                    "revenue_share": 1.0,
                    "critical": True,
                    "public_sector": True,
                }
            ]
        )
    )
    result = compute_customer_spof(g)
    assert result.status == Status.RED
    assert "mega" in result.drivers
    assert any("public_sector" in d for d in result.drivers)


def test_customer_metrics_absent_on_supply_only(load_example):
    g = load_example("single_supplier")
    assert compute_customer_hhi(g).inputs.get("optional_section_absent")
    assert compute_customer_spof(g).inputs.get("optional_section_absent")


# ---------------------------------------------------------------------------
# Energy + fixed-price contract convexity
# ---------------------------------------------------------------------------


def test_energy_margin_unrecovered():
    g = spec_to_networkx(
        _graph(
            energy={
                "cost_share": 0.20,
                "pass_through_pct": 0.25,
                "worst_on_record": 0.40,
                "source": {
                    "label": "EXAMPLE DATA — energy WOR placeholder",
                    "as_of": "2022-01-01",
                },
            }
        )
    )
    result = compute_energy_margin(g)
    # unrecovered = 0.20 * 0.75 = 0.15 → red at boundary (>)
    assert result.value == pytest.approx(0.15)
    assert result.status in {Status.AMBER, Status.RED}
    assert result.inputs["margin_hit_at_wor"] == pytest.approx(0.06)


def test_energy_unknown_flagged_fragile():
    g = spec_to_networkx(
        _graph(
            energy={
                "cost_share": 0.2,
                "pass_through_pct": None,
                "worst_on_record": 0.3,
                "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
            }
        )
    )
    result = compute_energy_margin(g)
    assert result.status == Status.RED
    assert result.inputs.get("fragile_unknown") is True


def test_fixed_price_input_cost_feeds_convexity():
    g = spec_to_networkx(
        _graph(
            inputs=[
                {
                    "id": "input_cost",
                    "worst_on_record": 0.2,
                    "lower_bound": 0.0,
                    "upper_bound": 1.0,
                    "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
                }
            ],
            contracts=[
                {
                    "id": "fixed_meal",
                    "counterparty": "RetailCo",
                    "revenue_share": 0.6,
                    "margin": 0.08,
                    "pricing": "fixed",
                    "input_cost_exposed": True,
                    "loss_exposure": 40.0,
                    "termination_notice_days": 90,
                    "source": {"label": "EXAMPLE", "as_of": "2020-01-01"},
                }
            ],
        )
    )
    result = compute_convexity(g)
    assert result.inputs.get("fixed_price_input_exposed") is True
    # Buffered-then-accelerating contract harm → fragile / not green
    assert result.status in {Status.AMBER, Status.RED}
    assert result.inputs.get("shape") == "fragile" or result.status != Status.GREEN


# ---------------------------------------------------------------------------
# ChillCo example loads with financial sections
# ---------------------------------------------------------------------------


def test_chillco_financial_sections_labelled_example():
    path = CLIENTS / "chillco" / "model" / "chillco.yaml"
    spec = load_graph_spec(path)
    assert spec.liquidity is not None
    assert spec.covenants
    assert spec.contracts
    assert spec.customers
    assert spec.energy is not None
    # All sources marked EXAMPLE
    assert "EXAMPLE" in (spec.liquidity.source.label if spec.liquidity.source else "")
    g = load_graph(path)
    results = run_all(g, Scenario(run_stress_ladder=True))
    assert "Concentration" in results
    cust_spof = next(r for r in results["Contagion"] if r.metric == "customer_spof")
    assert cust_spof.status != Status.NOT_TESTED
