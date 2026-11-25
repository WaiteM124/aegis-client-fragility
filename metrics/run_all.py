"""Run every structural-fragility metric and print grouped results.

Groups
------
  Concentration — HHI, monoculture, customer_hhi, customer_monoculture
  Contagion     — single points of failure, cascade depth, customer_spof
  Convexity     — convexity, ruin, distance_to_ruin, runway, energy_margin
  Optionality   — optionality, slack

Each group shows the status of its **worst** metric
(red > amber > not_tested > green). Ruin forces the Convexity group
(and the ruin line) to red. NOT_TESTED is never counted as a pass.

Optional financial-section metrics that return NOT_TESTED with
``optional_section_absent`` are excluded from group roll-up so supply-only
graphs keep identical group status (ADR-019). Customer and supplier
concentration stay as separate labelled results — never blended.

No weighted or blended single score is produced. Averaging would hide
danger and the units differ across metrics.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import networkx as nx

from metrics import (
    cascade_depth,
    convexity,
    customer_hhi,
    customer_monoculture,
    customer_spof,
    distance_to_ruin,
    energy_margin,
    hhi,
    monoculture,
    optionality,
    ruin,
    runway,
    slack,
)
from metrics import single_points_of_failure as spof
from metrics.cli_utils import add_common_args, build_scenario_from_args
from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import load_graph

GROUPS: list[tuple[str, list[tuple[str, Callable[..., MetricResult]]]]] = [
    (
        "Concentration",
        [
            ("HHI", hhi.compute),
            ("Monoculture", monoculture.compute),
            ("Customer HHI", customer_hhi.compute),
            ("Customer monoculture", customer_monoculture.compute),
        ],
    ),
    (
        "Contagion",
        [
            ("Single points of failure", spof.compute),
            ("Cascade depth", cascade_depth.compute),
            ("Customer SPOF", customer_spof.compute),
        ],
    ),
    (
        "Convexity",
        [
            ("Convexity", convexity.compute),
            ("Ruin", ruin.compute),
            ("Distance to ruin", distance_to_ruin.compute),
            ("Runway", runway.compute),
            ("Energy margin", energy_margin.compute),
        ],
    ),
    (
        "Optionality",
        [
            ("Optionality", optionality.compute),
            ("Slack", slack.compute),
        ],
    ),
]

# NOT_TESTED outranks GREEN so an untested probe cannot look like a pass.
_RANK = {
    Status.GREEN: 0,
    Status.NOT_TESTED: 1,
    Status.AMBER: 2,
    Status.RED: 3,
}


def _optional_section_absent(result: MetricResult) -> bool:
    """True when an optional financial section was omitted (ADR-019)."""
    inputs = result.inputs or {}
    return bool(inputs.get("optional_section_absent"))


def worst_status(results: list[MetricResult], *, ruin_forces_red: bool = False) -> Status:
    status = Status.GREEN
    for r in results:
        # Optional-section metrics absent on supply-only graphs must not
        # change group status (keeps existing evals / examples identical).
        if _optional_section_absent(r):
            continue
        if _RANK[r.status] > _RANK[status]:
            status = r.status
        if ruin_forces_red and r.metric == "ruin" and r.status == Status.RED:
            return Status.RED
    return status


def run_all(graph: nx.DiGraph, scenario: Scenario | None = None) -> dict[str, list[MetricResult]]:
    scenario = scenario or Scenario()
    out: dict[str, list[MetricResult]] = {}
    for group_name, metrics in GROUPS:
        out[group_name] = [fn(graph, scenario) for _label, fn in metrics]
    return out


def format_grouped(results: dict[str, list[MetricResult]]) -> str:
    lines: list[str] = []
    lines.append("Aegis structural-fragility metrics")
    lines.append("No forecast — structural weaknesses only. No blended score.")
    lines.append("")
    for group_name, _ in GROUPS:
        group_results = results[group_name]
        force = group_name == "Convexity"
        group_status = worst_status(group_results, ruin_forces_red=force)
        lines.append(f"=== {group_name}  [{group_status.value.upper()}] ===")
        for r in group_results:
            lines.append(
                f"  - {r.metric:24s}  value={r.value:<12}  status={r.status.value.upper()}"
            )
            if r.drivers:
                lines.append(f"      drivers: {', '.join(r.drivers)}")
            if r.status == Status.NOT_TESTED and r.meaning:
                # Surface the not-tested reason plainly
                reason = r.inputs.get("reason") if r.inputs else None
                if reason:
                    lines.append(f"      reason: {reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_graph_jobs(args: argparse.Namespace) -> list[tuple[Path, str | None]]:
    """Return (graph_path, client_id) jobs for this invocation."""
    if args.client:
        from metrics.client_pack import (
            check_backtest_cut_off,
            list_model_paths,
            load_client,
            load_sources_manifest,
        )

        client = load_client(args.client)
        manifest = load_sources_manifest(args.client)
        check_backtest_cut_off(client, manifest)
        models = list_model_paths(args.client)
        if not models:
            raise SystemExit(
                f"client {args.client!r} has no model/*.yaml graphs under "
                f"clients/{args.client}/model/"
            )
        if args.graph is not None:
            raise SystemExit("use either --client or --graph, not both")
        return [(p, args.client) for p in models]
    if args.graph is None:
        raise SystemExit("either --graph PATH or --client ID is required")
    return [(Path(args.graph), None)]


def _persist_record(
    *,
    graph_path: Path,
    scenario: Scenario,
    client_id: str | None,
    out_path: Path | None,
    store_path: Path | str | None,
    lock: bool,
    output_text: str,
) -> None:
    from metrics.client_pack import LockExistsError, client_dir, lock_map
    from metrics.run_record import build_run_record, write_run_record
    from metrics.store import load as store_load

    stress: bool | list[float]
    if scenario.stress_ladder is not None:
        stress = list(scenario.stress_ladder)
    else:
        stress = bool(scenario.run_stress_ladder)

    record = build_run_record(
        graph_path=graph_path,
        scenario=scenario,
        stress_ladder=stress if stress else False,
        survival_floor=scenario.survival_floor,
        client_id=client_id,
    )

    resolved_out = out_path
    if resolved_out is None and client_id is not None:
        runs_dir = client_dir(client_id) / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        resolved_out = runs_dir / f"{record['run_id']}.json"
    if resolved_out is None and store_path is not None:
        resolved_out = Path(store_path).with_suffix(".last_run.json")
    if resolved_out is None and lock:
        raise SystemExit("--lock requires --client (or --out) so a record path exists")
    assert resolved_out is not None
    write_run_record(record, resolved_out)

    if store_path is not None:
        inserted = store_load([resolved_out], db_path=Path(store_path))
        print(
            f"run record → {resolved_out} "
            f"(stored={inserted} new row(s) in {store_path})"
        )
    else:
        print(f"run record → {resolved_out}")

    if lock:
        if client_id is None:
            raise SystemExit("--lock requires --client")
        try:
            rec_dest, out_dest = lock_map(
                client_id=client_id,
                record_path=resolved_out,
                output_text=output_text,
            )
        except LockExistsError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"locked map → {rec_dest}")
        print(f"locked output → {out_dest}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run all Aegis structural-fragility metrics (no blended score)."
    )
    add_common_args(parser, graph_required=False)
    parser.add_argument(
        "--client",
        default=None,
        metavar="ID",
        help=(
            "Run models under clients/<ID>/model/, write the record into "
            "clients/<ID>/runs/, and set client_id on run_record.v2."
        ),
    )
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help=(
            "Ruin when remaining flow < FRAC × baseline at any ladder rung. "
            "Overrides graph YAML and the default (0.5)."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write one JSON run record (run_record.v1/v2) to PATH.",
    )
    parser.add_argument(
        "--store",
        nargs="?",
        const="data/aegis_runs.duckdb",
        default=None,
        metavar="DB",
        help=(
            "Write a run record and load it into local DuckDB (default "
            "data/aegis_runs.duckdb). Implies a temp JSON if --out is omitted."
        ),
    )
    parser.add_argument(
        "--lock",
        action="store_true",
        default=False,
        help=(
            "Copy the run record and rendered output into clients/<ID>/maps/ "
            "with a date stamp. Requires --client. Refuses to overwrite."
        ),
    )
    args = parser.parse_args(argv)

    jobs = _resolve_graph_jobs(args)
    scenario = build_scenario_from_args(args)
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})

    if args.lock and not args.client:
        raise SystemExit("--lock requires --client")

    # --client writes into clients/<id>/runs/ for traceability; --out/--store/--lock
    # also persist. Plain --graph with neither flag only prints.
    want_record = (
        args.out is not None
        or args.store is not None
        or args.client is not None
        or args.lock
    )

    for graph_path, client_id in jobs:
        graph = load_graph(graph_path)
        results = run_all(graph, scenario)
        text = format_grouped(results)
        if client_id and len(jobs) > 1:
            print(f"# model: {graph_path}")
        print(text, end="")

        if not want_record:
            continue
        _persist_record(
            graph_path=graph_path,
            scenario=scenario,
            client_id=client_id,
            out_path=args.out if len(jobs) == 1 else None,
            store_path=args.store,
            lock=bool(args.lock),
            output_text=text,
        )


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
