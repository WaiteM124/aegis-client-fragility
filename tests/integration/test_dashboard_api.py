"""
Integration tests for dashboard API endpoints (checkpoint 4, section 4).

Tests:
  - GET /api/v1/dashboard/stats  — empty database and after-pipeline
  - GET /api/v1/dashboard/events/{event_id}/trace — 404 and full trace
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import httpx
import pytest
from fastapi import FastAPI

from backend.api.routers import dashboard as dashboard_router
from backend.api.routers import events as events_router
from backend.assessment.service import AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.event_processing.worker import EventProcessingWorker
from backend.ingestion.service import IngestionService
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.message_bus.in_memory import InMemoryMessageBus
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.persistence.sqlite.event_store import SQLiteEventStore
from backend.retrieval.service import RetrievalService
from backend.shared.config import Settings
from backend.shared.models.clients import Client

# ── Minimal-app fixture (no worker) for simple stats/trace tests ──────────────


@pytest.fixture
async def mini_app():
    """
    Minimal FastAPI app with dashboard router only.
    Stores are empty — used for 'empty database' tests.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    event_store = SQLiteEventStore(db_path)
    await event_store.initialise()
    assessment_store = SQLiteAssessmentStore(db_path)
    await assessment_store.initialise()

    class _Container:
        pass

    container = _Container()
    container.event_store = event_store
    container.assessment_store = assessment_store

    app = FastAPI()
    app.state.container = container
    app.include_router(dashboard_router.router, prefix="/api/v1/dashboard")

    yield app

    await event_store.close()
    await assessment_store.close()
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


# ── Full-pipeline fixture (with worker) ───────────────────────────────────────


@pytest.fixture
async def pipeline_app():
    """
    Full pipeline app: event store, assessment store, in-memory bus, worker.
    Exposes both /api/v1/events and /api/v1/dashboard routes.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    event_store = SQLiteEventStore(db_path)
    await event_store.initialise()
    assessment_store = SQLiteAssessmentStore(db_path)
    await assessment_store.initialise()

    bus = InMemoryMessageBus()
    await bus.start()

    repo = LexicalKnowledgeRepository()
    await repo.index_document(
        document_id="doc-energy-001",
        content="Oil sanctions impact on Middle East energy sector and OPEC production.",
        source_type="industry_context",
        metadata={"id": "doc-energy-001"},
    )

    clients = [
        Client(
            id="c1",
            name="Test Energy Corp",
            industry="energy",
            geography=["middle_east"],
            keywords=["oil", "sanctions", "energy"],
        )
    ]

    retrieval = RetrievalService(repo)
    scorer = RiskScorer()
    model = DeterministicModelProvider()
    assessment_svc = AssessmentService(
        assessment_store=assessment_store,
        retrieval_service=retrieval,
        model_provider=model,
        risk_scorer=scorer,
        clients=clients,
        projects=[],
    )

    settings = Settings(
        events_topic="aegis-events",
        events_subscription="aegis-events-worker",
        dead_letter_topic="aegis-events-dlq",
        max_retry_attempts=2,
        retry_backoff_seconds=0.01,
        worker_concurrency=2,
    )

    worker = EventProcessingWorker(
        message_bus=bus,
        event_store=event_store,
        assessment_service=assessment_svc,
        settings=settings,
    )
    ingestion = IngestionService(event_store, bus)

    await worker.start()

    class _Container:
        pass

    container = _Container()
    container.event_store = event_store
    container.assessment_store = assessment_store
    container.ingestion_service = ingestion

    app = FastAPI()
    app.state.container = container
    app.include_router(events_router.router, prefix="/api/v1/events")
    app.include_router(dashboard_router.router, prefix="/api/v1/dashboard")

    yield app, event_store

    await worker.stop()
    await bus.stop()
    await event_store.close()
    await assessment_store.close()
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _wait_for_status(event_store, event_id: str, target: str, timeout: float = 5.0):
    """Poll until the event reaches the target status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        event = await event_store.get_event(event_id)
        if event and str(event.status) == target:
            return event
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Event {event_id} did not reach status={target!r} within {timeout}s")


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_stats_empty_database(mini_app):
    """GET /stats on an empty database returns zeroes without error."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mini_app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/dashboard/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 0
    assert data["total_assessments"] == 0
    assert data["clients_affected"] == 0
    assert isinstance(data["events_by_status"], dict)
    assert isinstance(data["events_by_severity"], dict)
    assert isinstance(data["assessments_by_risk_level"], dict)


async def test_trace_nonexistent_event_returns_404(mini_app):
    """GET /events/{event_id}/trace for a non-existent event returns HTTP 404."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mini_app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/dashboard/events/nonexistent-event-id/trace")

    assert resp.status_code == 404


async def test_stats_and_trace_after_pipeline(pipeline_app):
    """
    Full pipeline: submit event via POST /events, let worker process, then
    verify /stats returns total_events >= 1 and /trace returns all required fields.
    """
    app, event_store = pipeline_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Submit event via POST /api/v1/events
        resp = await client.post(
            "/api/v1/events",
            json={
                "source": "test",
                "title": "Major oil sanctions imposed on Middle East producer",
                "raw_content": (
                    "Sweeping oil and energy sanctions imposed on a major OPEC member following "
                    "military escalation. Energy markets in turmoil. Oil exports halted."
                ),
                "event_date": "2026-11-15T00:00:00",
                "affected_regions": ["middle_east"],
            },
        )
        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        event_id = resp.json()["event_id"]

        # 2. Wait for the worker to fully process the event
        await _wait_for_status(event_store, event_id, "assessed", timeout=10.0)

        # 3. Check /stats
        stats_resp = await client.get("/api/v1/dashboard/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_events"] >= 1, "stats.total_events must be >= 1 after submission"

        # 4. Check /events/{event_id}/trace
        trace_resp = await client.get(f"/api/v1/dashboard/events/{event_id}/trace")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()

        assert "event" in trace, "trace must contain 'event'"
        assert "classification" in trace, "trace must contain 'classification'"
        assert "assessments" in trace, "trace must contain 'assessments'"
        assert trace["event"]["id"] == event_id

        # Classification should have been produced
        assert trace["classification"] is not None, "classification must not be None"

        # At least one assessment expected (client c1 matches via oil/middle_east)
        assert len(trace["assessments"]) >= 1, "at least one assessment must be in trace"
        first = trace["assessments"][0]
        assert "assessment" in first
        assert "risk_score" in first
        assert "client_exposure" in first
