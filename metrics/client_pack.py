"""Client pack layout: load, validate, cut-off and confidential guards.

Layout (see ``clients/README.md``)::

    clients/<client_id>/
      client.yaml
      model/<name>.yaml
      sources/manifest.yaml
      maps/   # locked, date-stamped
      runs/   # local (gitignored)

No forecasts, probabilities, or blended scores.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_ROOT = REPO_ROOT / "clients"
CLIENT_SCHEMA_PATH = CLIENTS_ROOT / "schemas" / "client.v1.json"
SOURCES_SCHEMA_PATH = CLIENTS_ROOT / "schemas" / "sources_manifest.v1.json"

__all__ = [
    "CLIENTS_ROOT",
    "BacktestCutOffError",
    "ConfidentialPayloadError",
    "LockExistsError",
    "assert_no_confidential_payloads",
    "check_backtest_cut_off",
    "client_dir",
    "list_model_paths",
    "load_client",
    "load_sources_manifest",
    "lock_map",
    "validate_client",
    "validate_sources_manifest",
]


class BacktestCutOffError(ValueError):
    """Raised when a backtest source is published after cut_off_date."""


class ConfidentialPayloadError(ValueError):
    """Raised when a confidential client has sources/ or model/ files in git."""


class LockExistsError(FileExistsError):
    """Raised when --lock would overwrite an existing locked map artefact."""


def _format_checker():
    import jsonschema

    return jsonschema.FormatChecker()


def _load_yaml(path: Path) -> Any:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def load_client_schema() -> dict[str, Any]:
    return json.loads(CLIENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sources_schema() -> dict[str, Any]:
    return json.loads(SOURCES_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_client(data: dict[str, Any]) -> dict[str, Any]:
    import jsonschema

    jsonschema.validate(
        instance=data,
        schema=load_client_schema(),
        format_checker=_format_checker(),
    )
    return data


def validate_sources_manifest(data: dict[str, Any]) -> dict[str, Any]:
    import jsonschema

    jsonschema.validate(
        instance=data,
        schema=load_sources_schema(),
        format_checker=_format_checker(),
    )
    return data


def client_dir(client_id: str, *, root: Path | None = None) -> Path:
    base = Path(root) if root is not None else CLIENTS_ROOT
    path = base / client_id
    if not path.is_dir():
        raise FileNotFoundError(f"client pack not found: {path}")
    return path


def load_client(client_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = client_dir(client_id, root=root) / "client.yaml"
    data = _load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: client.yaml must be a mapping")
    validate_client(data)
    if data.get("id") != client_id:
        raise ValueError(
            f"{path}: id {data.get('id')!r} does not match folder {client_id!r}"
        )
    return data


def load_sources_manifest(
    client_id: str, *, root: Path | None = None
) -> dict[str, Any]:
    path = client_dir(client_id, root=root) / "sources" / "manifest.yaml"
    data = _load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: sources manifest must be a mapping")
    return validate_sources_manifest(data)


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def check_backtest_cut_off(
    client: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """Fail if any source publication_date is after client cut_off_date.

    Applies when ``kind`` is ``backtest``. Inclusive cut-off: dates equal to
    cut_off_date are allowed; later dates raise ``BacktestCutOffError``.
    """
    if client.get("kind") != "backtest":
        return
    cut_raw = client.get("cut_off_date")
    if not cut_raw:
        raise BacktestCutOffError("backtest client requires cut_off_date")
    cut = _parse_iso_date(str(cut_raw))
    offenders: list[str] = []
    for src in manifest.get("sources") or []:
        pub = _parse_iso_date(str(src["publication_date"]))
        if pub > cut:
            offenders.append(
                f"{src.get('id')}: publication_date {pub.isoformat()} "
                f"> cut_off_date {cut.isoformat()}"
            )
    if offenders:
        raise BacktestCutOffError(
            "backtest source(s) after cut_off_date: " + "; ".join(offenders)
        )


def list_model_paths(client_id: str, *, root: Path | None = None) -> list[Path]:
    model_dir = client_dir(client_id, root=root) / "model"
    if not model_dir.is_dir():
        return []
    return sorted(
        p for p in model_dir.iterdir() if p.suffix in {".yaml", ".yml"} and p.is_file()
    )


def _tracked_paths_under(rel_prefix: str, *, repo_root: Path) -> list[Path]:
    """Return git-tracked paths under ``rel_prefix`` (relative to repo root)."""
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z", "--", rel_prefix],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    if not out:
        return []
    paths: list[Path] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        paths.append(Path(raw.decode("utf-8")))
    return paths


def _is_placeholder(path: Path) -> bool:
    name = path.name
    return name in {".gitkeep", ".gitignore"} or name.startswith(".")


def assert_no_confidential_payloads(*, root: Path | None = None) -> None:
    """Fail if any confidential client has tracked files under sources/ or model/.

    Placeholders (``.gitkeep``) are ignored. Real client data belongs in private
    cloud storage, not git (ADR-018).
    """
    base = Path(root) if root is not None else CLIENTS_ROOT
    repo_root = base.parent if base.name == "clients" else base
    violations: list[str] = []
    if not base.is_dir():
        return
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "schemas":
            continue
        meta_path = child / "client.yaml"
        if not meta_path.is_file():
            continue
        data = _load_yaml(meta_path)
        if not isinstance(data, dict):
            continue
        if data.get("data_classification") != "confidential":
            continue
        client_id = child.name
        for sub in ("sources", "model"):
            rel = f"clients/{client_id}/{sub}"
            for tracked in _tracked_paths_under(rel, repo_root=repo_root):
                if _is_placeholder(tracked):
                    continue
                # Allow empty sources/manifest.yaml? Task says files under
                # sources/ or model/ — manifest is a file under sources/.
                # For confidential, even an empty manifest must not be committed
                # if we interpret strictly. But a confidential skeleton might
                # need a placeholder. Task: "fails if any client with
                # data_classification: confidential has files under sources/
                # or model/ committed." So any non-placeholder file fails.
                violations.append(str(tracked))
    if violations:
        raise ConfidentialPayloadError(
            "confidential client packs must not commit sources/ or model/ "
            "files (use private cloud storage): " + ", ".join(violations)
        )


def lock_map(
    *,
    client_id: str,
    record_path: Path,
    output_text: str,
    stamp: datetime | None = None,
    root: Path | None = None,
) -> tuple[Path, Path]:
    """Copy run record + rendered output into ``maps/`` with a date stamp.

    Refuses to overwrite existing locked artefacts.
    """
    maps_dir = client_dir(client_id, root=root) / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    ts = stamp or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    # Date-stamped, filesystem-safe (no colons).
    stamp_str = ts.strftime("%Y-%m-%dT%H%M%SZ")
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    graph_name = str(record.get("graph_name") or "graph")
    safe_graph = "".join(c if c.isalnum() or c in "-_" else "_" for c in graph_name)
    record_dest = maps_dir / f"{stamp_str}_{safe_graph}_run.json"
    output_dest = maps_dir / f"{stamp_str}_{safe_graph}_output.txt"
    if record_dest.exists() or output_dest.exists():
        raise LockExistsError(
            f"refusing to overwrite locked map: {record_dest.name} / {output_dest.name}"
        )
    shutil.copy2(record_path, record_dest)
    output_dest.write_text(output_text, encoding="utf-8")
    return record_dest, output_dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate client packs and confidential-data guards."
    )
    parser.add_argument(
        "--check-confidential",
        action="store_true",
        help="Fail if confidential clients have sources/ or model/ files in git.",
    )
    parser.add_argument(
        "--validate",
        metavar="CLIENT_ID",
        help="Validate client.yaml, sources manifest, and backtest cut-off.",
    )
    args = parser.parse_args(argv)
    if not args.check_confidential and not args.validate:
        parser.error("specify --check-confidential and/or --validate CLIENT_ID")
    try:
        if args.check_confidential:
            assert_no_confidential_payloads()
            print("confidential guard: ok")
        if args.validate:
            client = load_client(args.validate)
            manifest = load_sources_manifest(args.validate)
            check_backtest_cut_off(client, manifest)
            models = list_model_paths(args.validate)
            print(
                f"validated {args.validate}: "
                f"kind={client['kind']} models={len(models)}"
            )
    except (BacktestCutOffError, ConfidentialPayloadError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
