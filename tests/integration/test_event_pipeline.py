"""
Integration test: end-to-end event processing pipeline.

Verifies the vertical slice:
  submit event → publish → worker processes → assessment + risk score persisted

Uses an in-memory SQLite DB (":memory:" not viable with aiosqlite + multiple
connections, so we use a temp file) and the in-memory message bus.
No external services required.
"""

import asyncio
import os
import tempfile
import pytest

from backend.assessment.service import AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.event_processing.worker import EventProcessingWorker
from backend.ingestion.service import IngestionService, DuplicateEventError
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.message_bus.in_memory import InMemoryMessageBus
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.persistence.sqlite.event_store import SQLiteEventStore
from backend.retrieval.service import RetrievalService
from backend.shared.config import Settings
from backend.shared.models.clients import Client, Project
from backend.shared.models.events import EventStatus
from datetime import datetime


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
async def pipeline(db_path):
    """Assembled pipeline with real SQLite stores and in-memory bus."""
    # Stores
    event_store = SQLiteEventStore(db_path)
    await event_store.initialise()

    assessment_store = SQLiteAssessmentStore(db_path)
    await assessment_store.initialise()

    # Bus
    bus = InMemoryMessageBus()
    await bus.start()

    # Knowledge repo with one document
    repo = LexicalKnowledgeRepository()
    await repo.index_document(
        document_id="doc-1",
        content="Energy sector companies face oil price and sanctions risk in Middle East.",
        source_type="industry_context",
        metadata={"id": "doc-1"},
    )

    # Clients / projects
    clients = [
        Client(
            id="c1",
            name="Test Energy Corp",
            industry="energy",
            geography=["middle_east"],
            keywords=["oil", "sanctions", "energy"],
        )
    ]
    projects = [
        Project(
            id="p1",
            client_id="c1",
            name="Pipeline Project",
            description="Oil pipeline in Middle East region",
            geography=["middle_east"],
            keywords=["oil", "pipeline"],
        )
    ]

    # Services
    retrieval = RetrievalService(repo)
    scorer = RiskScorer()
    model = DeterministicModelProvider()
    assessment_svc = AssessmentService(
        assessment_store=assessment_store,
        retrieval_service=retrieval,
        model_provider=model,
        risk_scorer=scorer,
        clients=clients,
        projects=projects,
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

    yield {
        "ingestion": ingestion,
        "event_store": event_store,
        "assessment_store": assessment_store,
        "worker": worker,
        "bus": bus,
    }

    await worker.stop()
    await bus.stop()
    await event_store.close()
    await assessment_store.close()


# ── Tests ─────────────────────────────────────────────────────────────────────


async def _wait_for_status(event_store, event_id: str, target: str, timeout: float = 5.0):
    """Poll until the event reaches the target status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        event = await event_store.get_event(event_id)
        if event and str(event.status) == target:
            return event
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Event {event_id} did not reach status={target} within {timeout}s")


class TestEventPipeline:

    async def test_event_submitted_and_processed(self, pipeline):
        ingestion = pipeline["ingestion"]
        event_store = pipeline["event_store"]
        assessment_store = pipeline["assessment_store"]

        # Submit event
        event = await ingestion.ingest_event(
            source="test",
            title="Major oil sanctions imposed on OPEC member",
            raw_content=(
                "The international community has imposed sweeping oil sanctions on a major "
                "OPEC member following military escalation. Energy markets are in turmoil."
            ),
            event_date=datetime(2026, 11, 15),
            affected_regions=["middle_east"],
        )

        assert event.id
        assert str(event.status) == "pending"

        # Wait for async worker to process
        final_event = await _wait_for_status(event_store, event.id, "assessed")
        assert final_event is not None

        # Classification saved
        classification = await event_store.get_classification(event.id)
        assert classification is not None
        assert classification.event_id == event.id

        # Assessment saved
        assessments = await assessment_store.list_assessments(event_id=event.id)
        assert len(assessments) >= 1
        a = assessments[0]
        assert a.client_id == "c1"
        assert a.assessment_text
        assert len(a.key_risks) > 0

        # Risk score saved
        score = await assessment_store.get_risk_score(a.id)
        assert score is not None
        assert 0 <= score.overall_score <= 100
        assert score.scoring_algorithm_version

    async def test_idempotency_key_prevents_duplicate(self, pipeline):
        ingestion = pipeline["ingestion"]

        await ingestion.ingest_event(
            source="test",
            title="Duplicate event test",
            raw_content="First submission.",
            event_date=datetime(2026, 11, 1),
            idempotency_key="unique-key-xyz",
        )

        with pytest.raises(DuplicateEventError):
            await ingestion.ingest_event(
                source="test",
                title="Duplicate event test",
                raw_content="Second submission — same key.",
                event_date=datetime(2026, 11, 1),
                idempotency_key="unique-key-xyz",
            )

    async def test_correlation_id_propagated(self, pipeline):
        ingestion = pipeline["ingestion"]
        event_store = pipeline["event_store"]
        assessment_store = pipeline["assessment_store"]

        event = await ingestion.ingest_event(
            source="test",
            title="Oil pipeline sabotage reported in Middle East",
            raw_content="Reports of sabotage to major oil pipeline infrastructure.",
            event_date=datetime(2026, 11, 10),
            affected_regions=["middle_east"],
        )

        await _wait_for_status(event_store, event.id, "assessed")
        assessments = await assessment_store.list_assessments(event_id=event.id)
        for a in assessments:
            assert a.correlation_id == event.correlation_id
