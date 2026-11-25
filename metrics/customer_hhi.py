"""Herfindahl-Hirschman concentration of customer revenue shares (sales side).

Formula
-------
Let r_i be customer i's share of declared revenue (normalised to sum to 1):

    HHI_customers = Σ_i r_i²

Range: 1/n … 1 (single customer).

This metric is **labelled and separate** from supplier-side HHI. The two
are never blended into one concentration number (ADR-008 / ADR-019).

When the optional ``customers`` section is absent → NOT_TESTED with
``optional_section_absent`` (does not change Concentration group status).

Meaning
-------
Structural sales-side concentration. High means revenue depends on few
customers. Not a probability that a customer leaves.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.finance import (
    customer_shares,
    graph_customers,
    has_customers,
    section_absent_result,
)
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "customer_hhi"
VERSION = "1.0.0"


def _status(value: float, thresholds: Thresholds) -> Status:
    t = thresholds.hhi
    if value <= t.green_max:
        return Status.GREEN
    if value <= t.amber_max:
        return Status.AMBER
    return Status.RED


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    _ = scenario
    thresholds = thresholds or THRESHOLDS

    if not has_customers(graph):
        return section_absent_result(
            metric=METRIC, version=VERSION, section="customers", unit="index"
        )

    customers = graph_customers(graph)
    shares = customer_shares(customers)
    hhi = float(sum(s * s for s in shares.values()))
    n = max(len(shares), 1)
    equal = 1.0 / n
    drivers = [
        cid
        for cid, s in sorted(shares.items(), key=lambda kv: -kv[1])
        if s >= equal - 1e-12
    ]
    # Flag public-sector concentration drivers explicitly (Carillion use-case).
    for c in customers:
        if c.public_sector and c.id in drivers:
            drivers.append(f"public_sector:{c.id}")

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=hhi,
        status=_status(hhi, thresholds),
        drivers=drivers,
        inputs={
            "side": "customers",
            "shares": {k: round(v, 6) for k, v in shares.items()},
            "n_customers": n,
            "public_sector_ids": [c.id for c in customers if c.public_sector],
        },
        meaning=(
            f"Customer-revenue HHI={hhi:.4f} (sales side; separate from supplier HHI). "
            "High means concentrated dependence on few customers. "
            "Not a probability of customer loss."
        ),
        unit="index",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Compute customer-revenue HHI (sales side; structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
