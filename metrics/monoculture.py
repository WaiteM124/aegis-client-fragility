"""Monoculture: how much supply depends on one type, region, or technology.

Formula
-------
For each monoculture attribute a ∈ {type, region, technology}:
  bucket shares by attribute value using supplier supply shares s_i,
  then take M_a = max_bucket Σ_{i in bucket} s_i.
Overall monoculture score:

    M = max_a M_a

If an attribute is missing on a supplier, that supplier is skipped for
that attribute only.

Meaning
-------
High M means a large fraction of supply shares a single type, region, or
technology — a structural monoculture. Low M means attribute diversity.
This is not a forecast of which attribute will be hit.

Status defaults
---------------
  green  if M ≤ 0.40
  amber  if M ≤ 0.70
  red    otherwise
"""

from __future__ import annotations

import argparse
from collections import defaultdict

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import supplier_shares
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "monoculture"
VERSION = "1.0.0"
ATTRIBUTES = ("type", "region", "technology")


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
    shares = supplier_shares(graph)

    per_attr: dict[str, dict[str, float]] = {}
    best_attr = None
    best_bucket = None
    best_value = 0.0

    for attr in ATTRIBUTES:
        buckets: dict[str, float] = defaultdict(float)
        for sid, share in shares.items():
            val = graph.nodes[sid].get(attr)
            if val is None:
                continue
            buckets[str(val)] += share
        per_attr[attr] = dict(buckets)
        if not buckets:
            continue
        bucket, value = max(buckets.items(), key=lambda kv: kv[1])
        if value > best_value:
            best_value = value
            best_attr = attr
            best_bucket = bucket

    status = _status(best_value, thresholds)
    drivers: list[str] = []
    if best_attr and best_bucket is not None:
        drivers.append(f"{best_attr}:{best_bucket}")
        for sid, share in shares.items():
            if graph.nodes[sid].get(best_attr) == best_bucket:
                drivers.append(sid)

    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=float(best_value),
        status=status,
        drivers=drivers,
        inputs={
            "by_attribute": {a: {k: round(v, 6) for k, v in b.items()} for a, b in per_attr.items()},
            "dominant_attribute": best_attr,
            "dominant_bucket": best_bucket,
        },
        meaning=(
            f"Monoculture score={best_value:.4f}"
            + (f" via {best_attr}={best_bucket}" if best_attr else "")
            + ". High means one type/region/technology carries most supply share. "
            "Not a prediction of which attribute fails."
        ),
        unit="share",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Compute supply monoculture (structural).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
