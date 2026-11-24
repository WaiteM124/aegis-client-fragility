#!/usr/bin/env python3
"""One-shot generator for labelled eval cases. Not used by CI."""

from __future__ import annotations

from pathlib import Path

import yaml

CASES_DIR = Path(__file__).resolve().parent / "cases"


def _dump(case: dict) -> None:
    case_id = case["id"]
    path = CASES_DIR / f"{case_id}.yaml"
    path.write_text(
        yaml.safe_dump(case, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"wrote {path.name}")


def supplier(sid: str, typ: str, region: str, tech: str) -> dict:
    return {
        "id": sid,
        "kind": "supplier",
        "type": typ,
        "region": region,
        "technology": tech,
    }


def buyer(cid: str = "client") -> dict:
    return {"id": cid, "kind": "buyer"}


def edge(
    src: str,
    tgt: str,
    share: float,
    flow: float,
    capacity: float | None = None,
    buffer: float = 0.0,
    stress_response: str | None = None,
) -> dict:
    e: dict = {
        "source": src,
        "target": tgt,
        "share": share,
        "flow": flow,
        "capacity": capacity if capacity is not None else flow,
        "buffer": buffer,
    }
    if stress_response:
        e["stress_response"] = stress_response
    return e


def main() -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for old in CASES_DIR.glob("*.yaml"):
        old.unlink()

    cases: list[dict] = []

    # --- Single-supplier monoculture ---
    cases.append(
        {
            "id": "mono-001-single-supplier",
            "description": (
                "Single supplier carries 100% share — classic monoculture / HHI=1."
            ),
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["hhi", "monoculture", "slack"],
            "graph": {
                "name": "mono-001-single-supplier",
                "nodes": [
                    supplier("s1", "semiconductor", "asia", "cmos"),
                    buyer(),
                ],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0)],
            },
        }
    )
    cases.append(
        {
            "id": "mono-002-single-fuel",
            "description": "Single fuel supplier with zero buffer — concentration red.",
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["hhi", "monoculture", "optionality", "slack"],
            "graph": {
                "name": "mono-002-single-fuel",
                "nodes": [supplier("s1", "fuel", "gulf", "refine"), buyer()],
                "edges": [edge("s1", "client", 1.0, 80, 80, 0, "linear")],
            },
        }
    )
    cases.append(
        {
            "id": "mono-003-dominant-share",
            "description": (
                "Two suppliers but one holds 90% share — HHI and monoculture flag."
            ),
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["hhi", "monoculture"],
            "graph": {
                "name": "mono-003-dominant-share",
                "nodes": [
                    supplier("s1", "chip", "asia", "cmos"),
                    supplier("s2", "chip", "asia", "cmos"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.9, 90, 90, 0),
                    edge("s2", "client", 0.1, 10, 10, 0),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "mono-004-same-region-type",
            "description": (
                "Three equal-share suppliers, all same type and region — monoculture."
            ),
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["monoculture"],
            "graph": {
                "name": "mono-004-same-region-type",
                "nodes": [
                    supplier("s1", "api", "india", "ferment"),
                    supplier("s2", "api", "india", "ferment"),
                    supplier("s3", "api", "india", "ferment"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 1 / 3, 33.333, 40, 2),
                    edge("s2", "client", 1 / 3, 33.333, 40, 2),
                    edge("s3", "client", 1 / 3, 33.334, 40, 2),
                ],
            },
        }
    )

    # --- Hidden SPOF behind apparent redundancy ---
    cases.append(
        {
            "id": "spof-001-hidden-subtier",
            "description": (
                "Two tier-1 assemblers look redundant but share one sub-tier supplier."
            ),
            "weakness": "hidden_single_point_of_failure",
            "is_control": False,
            "detecting_metrics": ["single_points_of_failure", "hhi"],
            "graph": {
                "name": "spof-001-hidden-subtier",
                "nodes": [
                    supplier("subtier", "wafer", "asia", "fab"),
                    {
                        "id": "tier1_a",
                        "kind": "asset",
                        "type": "assembler",
                        "region": "asia",
                        "technology": "smt",
                    },
                    {
                        "id": "tier1_b",
                        "kind": "asset",
                        "type": "assembler",
                        "region": "europe",
                        "technology": "smt",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("subtier", "tier1_a", 0.5, 50, 60, 0),
                    edge("subtier", "tier1_b", 0.5, 50, 60, 0),
                    edge("tier1_a", "client", 0.5, 50, 60, 5),
                    edge("tier1_b", "client", 0.5, 50, 60, 5),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "spof-002-shared-hub",
            "description": (
                "Two suppliers feed one shared logistics hub before the client."
            ),
            "weakness": "hidden_single_point_of_failure",
            "is_control": False,
            "detecting_metrics": ["single_points_of_failure"],
            "graph": {
                "name": "spof-002-shared-hub",
                "nodes": [
                    supplier("s1", "ore", "africa", "mine"),
                    supplier("s2", "ore", "americas", "mine"),
                    {
                        "id": "hub",
                        "kind": "asset",
                        "type": "port",
                        "region": "europe",
                        "technology": "bulk",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s1", "hub", 0.5, 50, 60, 0),
                    edge("s2", "hub", 0.5, 50, 60, 0),
                    edge("hub", "client", 1.0, 100, 110, 5),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "spof-003-dual-route-shared-source",
            "description": (
                "Two parallel routes from one supplier — supplier is the hidden SPOF."
            ),
            "weakness": "hidden_single_point_of_failure",
            "is_control": False,
            "detecting_metrics": ["single_points_of_failure", "hhi", "monoculture"],
            "graph": {
                "name": "spof-003-dual-route-shared-source",
                "nodes": [
                    supplier("s1", "fuel", "gulf", "refine"),
                    {
                        "id": "route_n",
                        "kind": "route",
                        "type": "pipeline",
                        "region": "north",
                        "technology": "pipe",
                    },
                    {
                        "id": "route_s",
                        "kind": "route",
                        "type": "tanker",
                        "region": "south",
                        "technology": "ship",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s1", "route_n", 0.5, 50, 70, 10),
                    edge("route_n", "client", 0.5, 50, 70, 10),
                    edge("s1", "route_s", 0.5, 50, 70, 10),
                    edge("route_s", "client", 0.5, 50, 70, 10),
                ],
            },
        }
    )

    # --- Deep cascade chains ---
    cases.append(
        {
            "id": "cascade-001-depth2",
            "description": "A→B→client chain — cascade depth 2, dual SPOFs.",
            "weakness": "deep_cascade_chain",
            "is_control": False,
            "detecting_metrics": [
                "cascade_depth",
                "single_points_of_failure",
                "optionality",
                "slack",
            ],
            "graph": {
                "name": "cascade-001-depth2",
                "nodes": [
                    supplier("A", "ore", "africa", "open-pit"),
                    {
                        "id": "B",
                        "kind": "asset",
                        "type": "refinery",
                        "region": "africa",
                        "technology": "smelt",
                    },
                    buyer("C"),
                ],
                "edges": [
                    edge("A", "B", 1.0, 100, 100, 0),
                    edge("B", "C", 1.0, 100, 100, 0),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "cascade-002-depth3",
            "description": "Four-node chain — cascade depth 3 (amber).",
            "weakness": "deep_cascade_chain",
            "is_control": False,
            "detecting_metrics": ["cascade_depth", "single_points_of_failure"],
            "graph": {
                "name": "cascade-002-depth3",
                "nodes": [
                    supplier("n0", "raw", "asia", "extract"),
                    {
                        "id": "n1",
                        "kind": "asset",
                        "type": "mill",
                        "region": "asia",
                        "technology": "grind",
                    },
                    {
                        "id": "n2",
                        "kind": "asset",
                        "type": "plant",
                        "region": "asia",
                        "technology": "refine",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("n0", "n1", 1.0, 100, 100, 0),
                    edge("n1", "n2", 1.0, 100, 100, 0),
                    edge("n2", "client", 1.0, 100, 100, 0),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "cascade-003-depth4-red",
            "description": "Five-node chain — cascade depth 4 crosses red threshold.",
            "weakness": "deep_cascade_chain",
            "is_control": False,
            "detecting_metrics": ["cascade_depth", "single_points_of_failure"],
            "graph": {
                "name": "cascade-003-depth4-red",
                "nodes": [
                    supplier("n0", "raw", "asia", "extract"),
                    {
                        "id": "n1",
                        "kind": "asset",
                        "type": "mill",
                        "region": "asia",
                        "technology": "grind",
                    },
                    {
                        "id": "n2",
                        "kind": "asset",
                        "type": "plant",
                        "region": "asia",
                        "technology": "refine",
                    },
                    {
                        "id": "n3",
                        "kind": "route",
                        "type": "rail",
                        "region": "asia",
                        "technology": "freight",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("n0", "n1", 1.0, 100, 100, 0),
                    edge("n1", "n2", 1.0, 100, 100, 0),
                    edge("n2", "n3", 1.0, 100, 100, 0),
                    edge("n3", "client", 1.0, 100, 100, 0),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "cascade-004-branching-deep",
            "description": (
                "Two deep chains merge at client — longest cascade still deep."
            ),
            "weakness": "deep_cascade_chain",
            "is_control": False,
            "detecting_metrics": ["cascade_depth"],
            "graph": {
                "name": "cascade-004-branching-deep",
                "nodes": [
                    supplier("s_a", "metal", "africa", "mine"),
                    supplier("s_b", "polymer", "europe", "poly"),
                    {
                        "id": "a1",
                        "kind": "asset",
                        "type": "smelter",
                        "region": "africa",
                        "technology": "smelt",
                    },
                    {
                        "id": "a2",
                        "kind": "asset",
                        "type": "fab",
                        "region": "africa",
                        "technology": "cast",
                    },
                    {
                        "id": "b1",
                        "kind": "asset",
                        "type": "mixer",
                        "region": "europe",
                        "technology": "blend",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s_a", "a1", 0.6, 60, 60, 0),
                    edge("a1", "a2", 0.6, 60, 60, 0),
                    edge("a2", "client", 0.6, 60, 60, 0),
                    edge("s_b", "b1", 0.4, 40, 40, 0),
                    edge("b1", "client", 0.4, 40, 40, 0),
                ],
            },
        }
    )

    # --- Concave / fragile under stress ladder ---
    cases.append(
        {
            "id": "convex-001-buffered-fragile",
            "description": (
                "Buffer absorbs small shocks then loss accelerates — concave / fragile."
            ),
            "weakness": "concave_loss_ladder",
            "is_control": False,
            "detecting_metrics": ["convexity"],
            "graph": {
                "name": "convex-001-buffered-fragile",
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 15, "buffered")],
            },
        }
    )
    cases.append(
        {
            "id": "convex-002-cliff-fragile",
            "description": "Cliff stress profile — accelerating loss and ruin at 50%.",
            "weakness": "concave_loss_ladder",
            "is_control": False,
            "detecting_metrics": ["convexity", "ruin"],
            "graph": {
                "name": "convex-002-cliff-fragile",
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "cliff")],
            },
        }
    )
    cases.append(
        {
            "id": "convex-003-buffered-multi-edge",
            "description": (
                "Two buffered edges with shared fragility under the stress ladder."
            ),
            "weakness": "concave_loss_ladder",
            "is_control": False,
            "detecting_metrics": ["convexity"],
            "graph": {
                "name": "convex-003-buffered-multi-edge",
                "nodes": [
                    supplier("s1", "parts", "asia", "stamp"),
                    supplier("s2", "parts", "europe", "stamp"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.5, 50, 50, 12, "buffered"),
                    edge("s2", "client", 0.5, 50, 50, 12, "buffered"),
                ],
            },
        }
    )

    # --- Ruin below / just above 0.5 survival floor ---
    cases.append(
        {
            "id": "ruin-001-below-floor-cliff",
            "description": (
                "Cliff zeros flow at δ=0.5 — remaining below default 0.5 survival floor."
            ),
            "weakness": "ruin_below_survival_floor",
            "is_control": False,
            "detecting_metrics": ["ruin"],
            "graph": {
                "name": "ruin-001-below-floor-cliff",
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "cliff")],
            },
        }
    )
    cases.append(
        {
            "id": "ruin-002-below-floor-high-yaml",
            "description": (
                "Linear ladder leaves 50% remaining; YAML floor 0.6 → ruin (below floor)."
            ),
            "weakness": "ruin_below_survival_floor",
            "is_control": False,
            "detecting_metrics": ["ruin"],
            "graph": {
                "name": "ruin-002-below-floor-high-yaml",
                "survival_floor": 0.6,
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "linear")],
            },
        }
    )
    cases.append(
        {
            "id": "ruin-003-just-above-floor",
            "description": (
                "Linear ladder leaves exactly 50% remaining at default floor 0.5 — "
                "strict inequality means NOT ruin (just at/above floor)."
            ),
            "weakness": "ruin_just_above_survival_floor",
            "is_control": False,
            "detecting_metrics": [],
            "expected_metric_status": {"ruin": "green"},
            "graph": {
                "name": "ruin-003-just-above-floor",
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "linear")],
            },
        }
    )
    cases.append(
        {
            "id": "ruin-004-well-above-low-floor",
            "description": (
                "Client YAML floor 0.3; 50% remaining stays above floor — no ruin."
            ),
            "weakness": "ruin_just_above_survival_floor",
            "is_control": False,
            "detecting_metrics": [],
            "expected_metric_status": {"ruin": "green"},
            "graph": {
                "name": "ruin-004-well-above-low-floor",
                "survival_floor": 0.3,
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "linear")],
            },
        }
    )
    cases.append(
        {
            "id": "ruin-005-decelerating-still-ruins",
            "description": (
                "Decelerating profile is antifragile on convexity but remaining at "
                "δ=0.5 is 25% — still below the 0.5 survival floor."
            ),
            "weakness": "ruin_below_survival_floor",
            "is_control": False,
            "detecting_metrics": ["ruin"],
            "graph": {
                "name": "ruin-005-decelerating-still-ruins",
                "nodes": [supplier("s1", "commodity", "local", "bulk"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 100, 0, "decelerating")],
            },
        }
    )

    # --- Low optionality and slack ---
    cases.append(
        {
            "id": "opt-001-one-route",
            "description": "Single corridor via one route node — low optionality.",
            "weakness": "low_optionality_slack",
            "is_control": False,
            "detecting_metrics": ["optionality", "single_points_of_failure"],
            "graph": {
                "name": "opt-001-one-route",
                "nodes": [
                    supplier("s1", "fuel", "gulf", "refine"),
                    {
                        "id": "route_only",
                        "kind": "route",
                        "type": "pipeline",
                        "region": "north",
                        "technology": "pipe",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s1", "route_only", 1.0, 100, 110, 5),
                    edge("route_only", "client", 1.0, 100, 110, 5),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "opt-002-zero-slack",
            "description": "Capacity equals flow, buffer 0 — slack red.",
            "weakness": "low_optionality_slack",
            "is_control": False,
            "detecting_metrics": ["slack"],
            "graph": {
                "name": "opt-002-zero-slack",
                "nodes": [
                    supplier("s1", "parts", "asia", "cnc"),
                    supplier("s2", "parts", "europe", "cnc"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.5, 50, 50, 0),
                    edge("s2", "client", 0.5, 50, 50, 0),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "opt-003-tight-capacity",
            "description": "Slight headroom only — slack amber/red territory.",
            "weakness": "low_optionality_slack",
            "is_control": False,
            "detecting_metrics": ["slack"],
            "graph": {
                "name": "opt-003-tight-capacity",
                "nodes": [
                    supplier("s1", "chem", "asia", "batch"),
                    supplier("s2", "chem", "americas", "batch"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.5, 50, 52, 0),
                    edge("s2", "client", 0.5, 50, 52, 0),
                ],
            },
        }
    )

    # --- Robust controls (must NOT be flagged red) ---
    cases.append(
        {
            "id": "control-001-four-diversified",
            "description": (
                "Four equal diversified suppliers with slack — robust control."
            ),
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-001-four-diversified",
                "nodes": [
                    supplier("s1", "semiconductor", "asia", "cmos"),
                    supplier("s2", "optics", "europe", "photonics"),
                    supplier("s3", "chemicals", "americas", "bulk"),
                    supplier("s4", "logistics", "africa", "freight"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.25, 25, 40, 5),
                    edge("s2", "client", 0.25, 25, 40, 5),
                    edge("s3", "client", 0.25, 25, 40, 5),
                    edge("s4", "client", 0.25, 25, 40, 5),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "control-002-three-diversified",
            "description": "Three diversified suppliers with headroom — robust control.",
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-002-three-diversified",
                "nodes": [
                    supplier("s1", "steel", "europe", "blast"),
                    supplier("s2", "polymer", "americas", "poly"),
                    supplier("s3", "glass", "asia", "float"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 1 / 3, 33.3, 50, 8, "linear"),
                    edge("s2", "client", 1 / 3, 33.3, 50, 8, "linear"),
                    edge("s3", "client", 1 / 3, 33.4, 50, 8, "linear"),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "control-003-parallel-independent",
            "description": (
                "Two independent supplier→route→client corridors — no shared SPOF."
            ),
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-003-parallel-independent",
                "nodes": [
                    supplier("s1", "fuel", "gulf", "pipe_refine"),
                    supplier("s2", "biofuel", "north_sea", "ship_blend"),
                    {
                        "id": "route_n",
                        "kind": "route",
                        "type": "pipeline",
                        "region": "north",
                        "technology": "pipe",
                    },
                    {
                        "id": "route_s",
                        "kind": "route",
                        "type": "tanker",
                        "region": "south",
                        "technology": "ship",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s1", "route_n", 0.5, 50, 80, 15),
                    edge("route_n", "client", 0.5, 50, 80, 15),
                    edge("s2", "route_s", 0.5, 50, 80, 15),
                    edge("route_s", "client", 0.5, 50, 80, 15),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "control-004-five-equal",
            "description": "Five equal diversified suppliers — strong robust control.",
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-004-five-equal",
                "nodes": [
                    supplier("s1", "a", "r1", "t1"),
                    supplier("s2", "b", "r2", "t2"),
                    supplier("s3", "c", "r3", "t3"),
                    supplier("s4", "d", "r4", "t4"),
                    supplier("s5", "e", "r5", "t5"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.2, 20, 35, 6),
                    edge("s2", "client", 0.2, 20, 35, 6),
                    edge("s3", "client", 0.2, 20, 35, 6),
                    edge("s4", "client", 0.2, 20, 35, 6),
                    edge("s5", "client", 0.2, 20, 35, 6),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "control-005-redundant-deep",
            "description": (
                "Two short parallel chains from diversified suppliers — robust."
            ),
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-005-redundant-deep",
                "nodes": [
                    supplier("s1", "metal", "africa", "mine"),
                    supplier("s2", "polymer", "europe", "poly"),
                    {
                        "id": "a1",
                        "kind": "asset",
                        "type": "smelter",
                        "region": "africa",
                        "technology": "smelt",
                    },
                    {
                        "id": "b1",
                        "kind": "asset",
                        "type": "mixer",
                        "region": "europe",
                        "technology": "blend",
                    },
                    buyer(),
                ],
                "edges": [
                    edge("s1", "a1", 0.5, 50, 80, 20),
                    edge("a1", "client", 0.5, 50, 80, 20),
                    edge("s2", "b1", 0.5, 50, 80, 20),
                    edge("b1", "client", 0.5, 50, 80, 20),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "control-006-linear-buffered-diverse",
            "description": (
                "Four diversified linear edges with capacity headroom — robust."
            ),
            "weakness": "none",
            "is_control": True,
            "detecting_metrics": [],
            "graph": {
                "name": "control-006-linear-buffered-diverse",
                "nodes": [
                    supplier("s1", "alpha", "north", "x"),
                    supplier("s2", "beta", "south", "y"),
                    supplier("s3", "gamma", "east", "z"),
                    supplier("s4", "delta", "west", "w"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.25, 25, 50, 10, "linear"),
                    edge("s2", "client", 0.25, 25, 50, 10, "linear"),
                    edge("s3", "client", 0.25, 25, 50, 10, "linear"),
                    edge("s4", "client", 0.25, 25, 50, 10, "linear"),
                ],
            },
        }
    )

    # --- Extra coverage mixes ---
    cases.append(
        {
            "id": "mix-001-dual-concentrated",
            "description": "Two equal suppliers same everything — HHI amber, monoculture red.",
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["monoculture"],
            "graph": {
                "name": "mix-001-dual-concentrated",
                "nodes": [
                    supplier("s1", "chip", "taiwan", "cmos"),
                    supplier("s2", "chip", "taiwan", "cmos"),
                    buyer(),
                ],
                "edges": [
                    edge("s1", "client", 0.5, 50, 55, 1),
                    edge("s2", "client", 0.5, 50, 55, 1),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "mix-002-chain-with-bypass",
            "description": (
                "Chain with bypass — optionality green but concentration still red."
            ),
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["hhi", "monoculture"],
            "graph": {
                "name": "mix-002-chain-with-bypass",
                "nodes": [
                    supplier("A", "ore", "africa", "open-pit"),
                    {
                        "id": "B",
                        "kind": "asset",
                        "type": "refinery",
                        "region": "africa",
                        "technology": "smelt",
                    },
                    {
                        "id": "D",
                        "kind": "asset",
                        "type": "alt_refinery",
                        "region": "europe",
                        "technology": "smelt",
                    },
                    buyer("C"),
                ],
                "edges": [
                    edge("A", "B", 0.5, 50, 55, 5),
                    edge("B", "C", 0.5, 50, 55, 5),
                    edge("A", "D", 0.5, 50, 55, 5),
                    edge("D", "C", 0.5, 50, 55, 5),
                ],
            },
        }
    )
    cases.append(
        {
            "id": "mix-003-one-supplier-high-slack",
            "description": (
                "Single supplier but large slack — still concentration weakness."
            ),
            "weakness": "single_supplier_monoculture",
            "is_control": False,
            "detecting_metrics": ["hhi", "monoculture", "optionality"],
            "graph": {
                "name": "mix-003-one-supplier-high-slack",
                "nodes": [supplier("s1", "power", "nordic", "hydro"), buyer()],
                "edges": [edge("s1", "client", 1.0, 100, 200, 50, "linear")],
            },
        }
    )

    for case in cases:
        _dump(case)

    print(f"\nGenerated {len(cases)} cases in {CASES_DIR}")


if __name__ == "__main__":
    main()
