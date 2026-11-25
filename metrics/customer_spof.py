"""Sales-side single points of failure: critical or sole customers.

Formula
-------
A customer is a sales-side SPOF when:

  • they are marked ``critical: true``, or
  • they are the sole declared customer (n = 1), or
  • their normalised revenue share is ≥ 1.0 − ε (effectively sole).

Value = number of such SPOFs.

Status
------
  green  if count = 0
  red    if any SPOF is critical or sole (single dominant customer)
  amber  if SPOFs exist only via share dominance without critical flag
         (reserved; current rule treats sole / critical as red)

When ``customers`` absent → NOT_TESTED with ``optional_section_absent``.

Meaning
-------
Structural dependence on a single sales counterparty. Separate from
supply-side SPOF; never merged into one number. Not a probability that
the customer departs.
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

METRIC = "customer_spof"
VERSION = "1.0.0"


def find_customer_spofs(
    graph: nx.DiGraph,
) -> tuple[list[str], list[str]]:
    """Return (all_spof_ids, critical_or_sole_ids)."""
    customers = graph_customers(graph)
    if not customers:
        return [], []
    shares = customer_shares(customers)
    spofs: list[str] = []
    critical: list[str] = []
    sole = len(customers) == 1
    for c in customers:
        share = shares.get(c.id, 0.0)
        is_sole = sole or share >= 1.0 - 1e-12
        if c.critical or is_sole:
            spofs.append(c.id)
            critical.append(c.id)
        elif share >= 0.5:
            # Dominant but not declared critical — still a structural SPOF signal.
            spofs.append(c.id)
    return sorted(set(spofs)), sorted(set(critical))


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> MetricResult:
    _ = scenario
    _ = thresholds or THRESHOLDS

    if not has_customers(graph):
        return section_absent_result(
            metric=METRIC, version=VERSION, section="customers", unit="count"
        )

    customers = graph_customers(graph)
    shares = customer_shares(customers)
    spofs, critical = find_customer_spofs(graph)

    if not spofs:
        status = Status.GREEN
    elif critical:
        status = Status.RED
    else:
        status = Status.AMBER

    public = [c.id for c in customers if c.public_sector and c.id in spofs]
    drivers = list(spofs)
    for pid in public:
        drivers.append(f"public_sector:{pid}")

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(len(spofs)),
        status=status,
        drivers=drivers,
        inputs={
            "side": "customers",
            "spofs": spofs,
            "critical_or_sole": critical,
            "shares": {k: round(v, 6) for k, v in shares.items()},
            "public_sector_spofs": public,
        },
        meaning=(
            f"Customer SPOFs={len(spofs)} (sales side; separate from supplier SPOF). "
            "Critical or sole customers are a hard structural red flag. "
            "Not a probability of counterparty loss."
        ),
        unit="count",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Sales-side customer single points of failure (structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
