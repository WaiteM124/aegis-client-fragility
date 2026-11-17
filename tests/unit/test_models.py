"""
Unit tests for Pydantic data models.

Validates that models enforce constraints, serialise correctly,
and round-trip through JSON without data loss.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.shared.models.events import Event, EventStatus, EventSeverity, EventCategory, EventClassification
from backend.shared.models.clients import Client, Project, ClientExposure, RiskProfile, ProjectStatus
from backend.shared.models.assessment import ImpactAssessment, EvidenceReference
from backend.shared.models.scoring import RiskScore, RiskLevel


# ── Event ─────────────────────────────────────────────────────────────────────

class TestEvent:
    def test_creates_with_required_fields(self):
        event = Event(
            source="test",
            title="Test Event",
            raw_content="Something happened in the world.",
            event_date=datetime(2026, 11, 1, 12, 0),
        )
        assert event.id
        assert event.correlation_id
        assert event.status == EventStatus.PENDING

    def test_id_is_uuid_format(self):
        event = Event(
            source="test",
            title="Test Event",
            raw_content="Content",
            event_date=datetime(2026, 11, 1),
        )
        import uuid
        uuid.UUID(event.id)  # raises if not valid UUID

    def test_idempotency_key_stored(self):
        event = Event(
            source="test",
            title="Test",
            raw_content="Content",
            event_date=datetime(2026, 11, 1),
            idempotency_key="my-unique-key-123",
        )
        assert event.idempotency_key == "my-unique-key-123"

    def test_json_round_trip(self):
        event = Event(
            source="reuters",
            title="Tensions rise in disputed region",
            raw_content="Multiple governments have issued statements.",
            event_date=datetime(2026, 11, 15, 8, 0),
            affected_regions=["middle_east", "europe"],
            tags=["geopolitical", "conflict"],
        )
        serialised = event.model_dump(mode="json")
        restored = Event.model_validate(serialised)
        assert restored.id == event.id
        assert restored.affected_regions == ["middle_east", "europe"]

    def test_status_enum_values(self):
        event = Event(
            source="test",
            title="Test",
            raw_content="Content",
            event_date=datetime(2026, 11, 1),
            status=EventStatus.ASSESSED,
        )
        assert event.status == "assessed"


# ── EventClassification ───────────────────────────────────────────────────────

class TestEventClassification:
    def test_confidence_bounded(self):
        with pytest.raises(ValidationError):
            EventClassification(
                event_id="e1",
                category=EventCategory.GEOPOLITICAL,
                severity=EventSeverity.HIGH,
                confidence=1.5,  # out of range
                classifier_version="1.0.0",
            )

    def test_valid_classification(self):
        cls = EventClassification(
            event_id="e1",
            category=EventCategory.CYBER,
            severity=EventSeverity.CRITICAL,
            confidence=0.87,
            classifier_version="1.0.0",
        )
        assert cls.category == "cyber"
        assert cls.severity == "critical"


# ── Client ────────────────────────────────────────────────────────────────────

class TestClient:
    def test_defaults(self):
        client = Client(name="Acme Corp", industry="technology")
        assert client.risk_profile == "moderate"
        assert client.active is True
        assert client.geography == []

    def test_keywords_stored(self):
        client = Client(
            name="Acme",
            industry="energy",
            keywords=["oil", "gas", "pipeline"],
        )
        assert "pipeline" in client.keywords


# ── RiskScore ─────────────────────────────────────────────────────────────────

class TestRiskScore:
    def test_score_range(self):
        score = RiskScore(
            assessment_id="a1",
            event_id="e1",
            client_id="c1",
            overall_score=75.5,
            severity_component=75.0,
            exposure_component=60.0,
            confidence_component=80.0,
            risk_level=RiskLevel.HIGH,
            scoring_algorithm_version="1.0.0",
        )
        assert 0 <= score.overall_score <= 100

    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            RiskScore(
                assessment_id="a1",
                event_id="e1",
                client_id="c1",
                overall_score=105.0,  # > 100
                severity_component=75.0,
                exposure_component=60.0,
                confidence_component=80.0,
                risk_level=RiskLevel.HIGH,
                scoring_algorithm_version="1.0.0",
            )


# ── EvidenceReference ─────────────────────────────────────────────────────────

class TestEvidenceReference:
    def test_relevance_score_bounded(self):
        with pytest.raises(ValidationError):
            EvidenceReference(
                source_document_id="doc1",
                source_type="regional_profile",
                content_excerpt="Some text.",
                relevance_score=1.5,  # > 1.0
                retrieval_strategy="lexical_bm25",
            )

    def test_valid_evidence(self):
        ref = EvidenceReference(
            source_document_id="doc1",
            source_type="client_profile",
            content_excerpt="Client operates in energy sector across MENA.",
            relevance_score=0.82,
            retrieval_strategy="lexical_bm25",
        )
        assert ref.relevance_score == 0.82
