"""Shared fixtures for structural-fragility metric tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from metrics.graph_loader import load_graph

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def load_example(examples_dir: Path):
    def _load(name: str):
        path = examples_dir / name
        if not path.suffix:
            path = examples_dir / f"{name}.yaml"
        return load_graph(path)

    return _load
