"""Herfindahl-Hirschman concentration of supply shares.

Formula
-------
Let s_i be supplier i's share of total supply into the client
(from edge ``share`` leaving each supplier, normalised to sum to 1).

    HHI = Σ_i s_i²

Range: 1/n (n equal suppliers) … 1 (single supplier).

Meaning
-------
HHI is a structural concentration reading of the dependency graph.
It does not forecast disruption likelihood. High HHI means supply is
concentrated in few suppliers (structurally fragile to whatever hits
those nodes). Low HHI means shares are dispersed.

Status defaults (see ``metrics.thresholds``)
-------------------------------------------
  green  if HHI ≤ 0.25
  amber  if HHI ≤ 0.50
  red    otherwise
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import supplier_shares
from metrics.thresholds import THRESHOLDS, Thresholds

METRIC = "hhi"
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
    """Compute HHI of supplier supply shares on the intact graph structure.

    Scenario shocks are ignored for HHI: concentration is a property of
    the declared share structure, not of a predicted event.
    """
    _ = scenario  # structural metric; shocks do not redefine declared shares
    thresholds = thresholds or THRESHOLDS
    shares = supplier_shares(graph)
    hhi = float(sum(s * s for s in shares.values()))
    # Drivers: suppliers with above-equal share, largest first
    n = max(len(shares), 1)
    equal = 1.0 / n
    drivers = [
        sid
        for sid, s in sorted(shares.items(), key=lambda kv: -kv[1])
        if s >= equal - 1e-12
    ]
    status = _status(hhi, thresholds)
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=hhi,
        status=status,
        drivers=drivers,
        inputs={"shares": {k: round(v, 6) for k, v in shares.items()}, "n_suppliers": n},
        meaning=(
            f"Supply-share HHI={hhi:.4f}. "
            "High means concentrated structural dependence on few suppliers; "
            "low means dispersed shares. Not a probability of disruption."
        ),
        unit="index",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Compute supply-share HHI (structural).")
    add_common_args(parser)
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
