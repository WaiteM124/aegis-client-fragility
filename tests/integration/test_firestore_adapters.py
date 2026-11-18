"""
Integration tests for Firestore persistence adapters (checkpoint 4, section 5).

All tests are skipped unless FIRESTORE_EMULATOR_HOST is set, which requires
the Firestore emulator to be running (see docker-compose --profile firestore).

Run with:
    docker-compose --profile firestore up -d
    FIRESTORE_EMULATOR_HOST=localhost:8086 pytest tests/integration/test_firestore_adapters.py
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

from backend.shared.models.assessment import EvidenceReference, ImpactAssessment
from backend.shared.models.clients import ClientExposure
from backend.shared.models.events import Event, EventCategory, EventClassification, EventSeverity
from backend.shared.models.scoring import RiskScore

_SKIP = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="FIRESTORE_EMULATOR_HOST not set — Firestore emulator not running",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def firestore_db():
    """Return an injected Firestore client pointed at the emulator."""
    import google.cloud.firestore as firestore  # noqa: PLC0415

    db = firestore.Client(project="aegis-test")
    yield db


@pytest.fixture
async def event_store(firestore_db):
    from backend.persistence.firestore.event_store import FirestoreEventStore  # noqa: PLC0415

    store = FirestoreEventStore(firestore_db)
    await store.initialise()
    return store


@pytest.fixture
async def assessment_store(firestore_db):
    from backend.persistence.firestore.assessment_store import FirestoreAssessmentStore  # noqa: PLC0415

    store = FirestoreAssessmentStore(firestore_db)
    await store.initialise()
    return store


def _make_event(**kwargs) -> Event:
    defaults = dict(
        source="test",
        title="Test Event",
        raw_content="Test content for Firestore adapter tests.",
        event_date=datetime(2026, 11, 15),
        affected_regions=["europe"],
    )
    defaults.update(kwargs)
    return Event(**defaults)


# ── Tests ─────────────────────────────────────────────────────────────────────


@_SKIP
async def test_save_and_retrieve_event(event_store):
    """Event saved to Firestore can be retrieved by ID."""
    event = _make_event(title="Firestore save/retrieve test")
    await event_store.save_event(event)

    retrieved = await event_store.get_event(event.id)
    assert retrieved is not None
    assert retrieved.id == event.id
    assert retrieved.title == event.title
    assert retrieved.affected_regions == event.affected_regions


@_SKIP
async def test_event_exists_by_idempotency_key(event_store):
    """event_exists() returns True for a saved event's idempotency key."""
    event = _make_event(idempotency_key="firestore-idem-key-001")
    await event_store.save_event(event)

    exists = await event_store.event_exists("firestore-idem-key-001")
    assert exists is True

    not_exists = await event_store.event_exists("firestore-idem-key-does-not-exist")
    assert not_exists is False


@_SKIP
async def test_save_and_retrieve_assessment(assessment_store):
    """Assessment saved to Firestore can be retrieved by ID."""
    assessment = ImpactAssessment(
        event_id="fs-event-001",
        client_id="fs-client-001",
        correlation_id="fs-corr-001",
        assessment_text="Firestore test assessment.",
        key_risks=["Risk A", "Risk B"],
        recommended_actions=["Action 1"],
        evidence_references=[],
        model_provider="deterministic",
        model_version="rules-v1",
        raw_model_output={"assessment_text": "Firestore test assessment."},
    )
    await assessment_store.save_assessment(assessment)

    retrieved = await assessment_store.get_assessment(assessment.id)
    assert retrieved is not None
    assert retrieved.id == assessment.id
    assert retrieved.event_id == assessment.event_id
    assert retrieved.client_id == assessment.client_id
    assert retrieved.key_risks == assessment.key_risks


@_SKIP
async def test_save_and_retrieve_risk_score(assessment_store):
    """RiskScore saved to Firestore can be retrieved by assessment ID."""
    score = RiskScore(
        assessment_id="fs-assessment-001",
        event_id="fs-event-001",
        client_id="fs-client-001",
        overall_score=72.5,
        severity_component=35.0,
        exposure_component=25.0,
        confidence_component=12.5,
        risk_level="HIGH",
        scoring_algorithm_version="1.0",
        factors={"severity": "high", "exposure": "significant"},
    )
    await assessment_store.save_risk_score(score)

    retrieved = await assessment_store.get_risk_score("fs-assessment-001")
    assert retrieved is not None
    assert retrieved.assessment_id == "fs-assessment-001"
    assert abs(retrieved.overall_score - 72.5) < 0.001
    assert str(retrieved.risk_level) == "HIGH"
