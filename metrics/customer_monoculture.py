"""Sales-side monoculture: customer type, region, or public-sector bucket.

Formula
-------
For each attribute a ∈ {type, region, public_sector}:
  bucket customer revenue shares, take M_a = max bucket share.
Overall:

    M = max_a M_a

``public_sector`` buckets are ``true`` / ``false`` (government counterparty
tag — needed for Carillion-style exposure). Separate from supplier
monoculture; never blended (ADR-019).

When ``customers`` absent → NOT_TESTED with ``optional_section_absent``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.finance import (
    customer_shares,
    graph_customers,
    has_customers,
    section_absent_result,
)
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "customer_monoculture"
VERSION = "1.0.0"
ATTRIBUTES = ("type", "region", "public_sector")


def _status(value: float, thresholds: Thresholds) -> Status:
    t = thresholds.monoculture
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
            metric=METRIC, version=VERSION, section="customers", unit="share"
        )

    customers = graph_customers(graph)
    shares = customer_shares(customers)
    by_id = {c.id: c for c in customers}

    per_attr: dict[str, dict[str, float]] = {}
    best_attr = None
    best_bucket = None
    best_value = 0.0

    for attr in ATTRIBUTES:
        buckets: dict[str, float] = defaultdict(float)
        for cid, share in shares.items():
            cust = by_id[cid]
            if attr == "public_sector":
                val = "true" if cust.public_sector else "false"
            else:
                val = getattr(cust, attr, None)
                if val is None:
                    continue
                val = str(val)
            buckets[val] += share
        per_attr[attr] = dict(buckets)
        if not buckets:
            continue
        bucket, value = max(buckets.items(), key=lambda kv: kv[1])
        if value > best_value:
            best_value = value
            best_attr = attr
            best_bucket = bucket

    drivers: list[str] = []
    if best_attr and best_bucket is not None:
        drivers.append(f"{best_attr}:{best_bucket}")
        for cid, share in shares.items():
            cust = by_id[cid]
            if best_attr == "public_sector":
                match = ("true" if cust.public_sector else "false") == best_bucket
            else:
                match = str(getattr(cust, best_attr, None)) == best_bucket
            if match:
                drivers.append(cid)

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(best_value),
        status=_status(best_value, thresholds),
        drivers=drivers,
        inputs={
            "side": "customers",
            "by_attribute": {
                a: {k: round(v, 6) for k, v in b.items()} for a, b in per_attr.items()
            },
            "dominant_attribute": best_attr,
            "dominant_bucket": best_bucket,
        },
        meaning=(
            f"Customer monoculture={best_value:.4f}"
            + (f" via {best_attr}={best_bucket}" if best_attr else "")
            + " (sales side; separate from supplier monoculture). "
            "Not a prediction of which attribute is hit."
        ),
        unit="share",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(
        description="Compute customer monoculture (sales side; structural)."
    )
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
