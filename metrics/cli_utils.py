"""Shared CLI helpers for individually runnable metric modules."""

from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx

from metrics.contracts import EdgeShock, NodeShock, Scenario
from metrics.graph_loader import load_graph


def build_scenario_from_args(args: argparse.Namespace) -> Scenario:
    node_shocks: list[NodeShock] = []
    for item in getattr(args, "shock_node", []) or []:
        # format: node_id[:intensity]
        if ":" in item:
            nid, raw = item.split(":", 1)
            node_shocks.append(NodeShock(node_id=nid, intensity=float(raw)))
        else:
            node_shocks.append(NodeShock(node_id=item, intensity=1.0))

    edge_shocks: list[EdgeShock] = []
    for item in getattr(args, "shock_edge", []) or []:
        # format: source>target[:intensity]
        if ":" in item:
            core, raw = item.rsplit(":", 1)
            intensity = float(raw)
        else:
            core, intensity = item, 1.0
        if ">" not in core:
            raise SystemExit(f"shock-edge must look like source>target[:intensity], got {item!r}")
        src, tgt = core.split(">", 1)
        edge_shocks.append(EdgeShock(source=src, target=tgt, intensity=intensity))

    return Scenario(
        name=getattr(args, "scenario_name", None) or "cli",
        node_shocks=node_shocks,
        edge_shocks=edge_shocks,
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--graph",
        required=True,
        type=Path,
        help="Path to a YAML dependency graph",
    )
    parser.add_argument(
        "--shock-node",
        action="append",
        default=[],
        metavar="NODE[:INTENSITY]",
        help="Structural node shock (repeatable). Intensity in [0,1], default 1.",
    )
    parser.add_argument(
        "--shock-edge",
        action="append",
        default=[],
        metavar="SRC>TGT[:INTENSITY]",
        help="Structural edge shock (repeatable). Intensity in [0,1], default 1.",
    )


def load_graph_and_scenario(args: argparse.Namespace) -> tuple[nx.DiGraph, Scenario]:
    graph = load_graph(args.graph)
    scenario = build_scenario_from_args(args)
    return graph, scenario
