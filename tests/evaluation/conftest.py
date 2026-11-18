"""Shared fixtures and helpers for evaluation tests."""
from __future__ import annotations

import json
import pytest
from datetime import datetime
from pathlib import Path

from backend.assessment.service import AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.event_processing.classifier import RuleBasedClassifier
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.retrieval.service import RetrievalService
from backend.shared.models.clients import Client
from backend.shared.models.events import Event


def make_event(ed: dict) -> Event:
    """Construct an Event from an evaluation dataset dict."""
    return Event(
        source=ed.get("source", "synthetic_evaluation"),
        title=ed["title"],
        raw_content=ed["raw_content"],
        event_date=datetime.fromisoformat(ed.get("event_date", "2026-01-15T00:00:00")),
        affected_regions=ed["affected_regions"],
    )


@pytest.fixture
async def pipeline(tmp_path):
    """Full assessment pipeline fixture backed by a temporary SQLite store."""
    clients_data = json.loads(Path("data/synthetic/clients.json").read_text())
    clients = [Client.model_validate(c) for c in clients_data]
    store = SQLiteAssessmentStore(str(tmp_path / "eval.db"))
    await store.initialise()
    repo = LexicalKnowledgeRepository()
    await repo.load_from_directory("data/synthetic")
    svc = AssessmentService(
        assessment_store=store,
        retrieval_service=RetrievalService(repo),
        model_provider=DeterministicModelProvider(),
        risk_scorer=RiskScorer(),
        clients=clients,
        projects=[],
    )
    clf = RuleBasedClassifier()
    yield clf, svc, store
    await store.close()
