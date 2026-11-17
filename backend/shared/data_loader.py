"""
Load synthetic clients and projects from JSON files.

The loaded objects are injected into services at startup.
They are intentionally static during a single run; a production
version would query a client store via ClientStorePort.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models.clients import Client, Project
from .logging import get_logger

logger = get_logger("data_loader")


async def load_synthetic_data(
    data_dir: str,
) -> tuple[list[Client], list[Project]]:
    """
    Read clients.json and projects.json from ``data_dir`` and return
    validated model instances.  Missing files produce an empty list and
    a warning, not an error.
    """
    path = Path(data_dir)
    clients: list[Client] = []
    projects: list[Project] = []

    clients_file = path / "clients.json"
    if clients_file.exists():
        with open(clients_file, encoding="utf-8") as fh:
            raw = json.load(fh)
        clients = [Client.model_validate(c) for c in raw]
        logger.info("Synthetic clients loaded", extra={"count": len(clients)})
    else:
        logger.warning("clients.json not found", extra={"path": str(clients_file)})

    projects_file = path / "projects.json"
    if projects_file.exists():
        with open(projects_file, encoding="utf-8") as fh:
            raw = json.load(fh)
        projects = [Project.model_validate(p) for p in raw]
        logger.info("Synthetic projects loaded", extra={"count": len(projects)})
    else:
        logger.warning("projects.json not found", extra={"path": str(projects_file)})

    return clients, projects
