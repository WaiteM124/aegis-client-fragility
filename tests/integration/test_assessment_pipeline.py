"""
Integration tests for the assessment pipeline (checkpoint 3).

Covers:
  - Successful end-to-end assessment with evidence retrieval
  - No matching clients returns empty list
  - Empty knowledge base produces assessment with no evidence
  - Model validation failure is caught per-client, not propagated
  - Citation validation drops references to non-existent documents
"""

from __future__ import annotations

import os
import tempfile
from typing import Type
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from backend.assessment.service import AssessmentOutput, AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.retrieval.service import RetrievalService
from backend.shared.models.assessment import EvidenceReference
from backend.shared.models.clients import Client, Project
from backend.shared.models.events import Event, EventClassification, EventCategory, EventSeverity
from backend.shared.ports.model_provider import ModelProviderPort
from datetime import datetime


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _make_event(**kwargs) -> Event:
    defaults = dict(
        source="test",
        title="Major cyber attack on financial infrastructure",
        raw_content=(
            "A sophisticated cyber attack has targeted major investment banking "
            "systems across Europe. Financial data has been compromised and "
            "trading operations disrupted. Sanctions and regulatory responses expected."
        ),
        event_date=datetime(2026, 11, 15),
        affected_regions=["europe"],
    )
    defaults.update(kwargs)
    return Event(**defaults)


def _make_classification(event: Event) -> EventClassification:
    return EventClassification(
        event_id=event.id,
        category=EventCategory.CYBER,
        severity=EventSeverity.HIGH,
        confidence=0.85,
        classifier_version="1.0",
    )


def _make_client(**kwargs) -> Client:
    defaults = dict(
        id="client-001",
        name="Meridian Investment Bank",
        industry="investment_banking",
        geography=["europe"],
        keywords=["cyber", "financial", "banking", "sanctions"],
    )
    defaults.update(kwargs)
    return Client(**defaults)


@pytest.fixture
async def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
async def store(db_path):
    s = SQLiteAssessmentStore(db_path)
    await s.initialise()
    yield s
    await s.close()


# ── Test classes ──────────────────────────────────────────────────────────────


class TestSuccessfulAssessment:

    @pytest.fixture
    async def repo(self):
        r = LexicalKnowledgeRepository()
        await r.index_document(
            document_id="doc-001",
            content=(
                "Cyber attacks targeting investment banking infrastructure in Europe have "
                "increased significantly. Financial institutions must review their network "
                "security posture and implement enhanced monitoring for suspicious activity. "
                "Sanctions from regulatory bodies may follow significant breaches affecting "
                "consumer financial data."
            ),
            source_type="intelligence_report",
            metadata={"id": "doc-001"},
        )
        await r.index_document(
            document_id="doc-002",
            content=(
                "European banking regulators have issued guidance on cyber resilience "
                "requirements following a series of coordinated attacks on financial market "
                "infrastructure. Banks are required to maintain incident response plans and "
                "conduct regular penetration testing of trading systems."
            ),
            source_type="regulatory_guidance",
            metadata={"id": "doc-002"},
        )
        await r.index_document(
            document_id="doc-003",
            content=(
                "Investment banks operating in Europe face elevated operational risk due to "
                "geopolitical tensions and state-sponsored cyber threat actors. Sanctions "
                "exposure and cross-border regulatory compliance are primary concerns for "
                "risk managers at major financial institutions."
            ),
            source_type="risk_assessment",
            metadata={"id": "doc-003"},
        )
        return r

    @pytest.fixture
    async def service(self, repo, store):
        retrieval = RetrievalService(repo)
        scorer = RiskScorer()
        model = DeterministicModelProvider()
        client = _make_client()
        svc = AssessmentService(
            assessment_store=store,
            retrieval_service=retrieval,
            model_provider=model,
            risk_scorer=scorer,
            clients=[client],
            projects=[],
        )
        return svc, store, repo

    async def test_at_least_one_assessment_returned(self, service):
        svc, store, repo = service
        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1

    async def test_evidence_references_non_empty_and_valid(self, service):
        svc, store, repo = service
        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1
        a = assessments[0]
        assert len(a.evidence_references) > 0

        # All source_document_ids must be in the index
        for ref in a.evidence_references:
            assert await repo.document_exists(ref.source_document_id), (
                f"Reference to unknown doc: {ref.source_document_id}"
            )

    async def test_model_provider_name(self, service):
        svc, store, repo = service
        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1
        assert assessments[0].model_provider == "deterministic"

    async def test_correlation_id_propagated(self, service):
        svc, store, repo = service
        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1
        assert assessments[0].correlation_id == event.correlation_id

    async def test_risk_score_persisted(self, service):
        svc, store, repo = service
        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1
        risk_score = await store.get_risk_score(assessments[0].id)
        assert risk_score is not None
        assert 0 <= risk_score.overall_score <= 100


class TestNoMatchingClients:

    async def test_returns_empty_list_without_raising(self, store):
        repo = LexicalKnowledgeRepository()
        await repo.index_document(
            document_id="doc-energy-001",
            content="Oil sanctions affecting energy companies in the Middle East.",
            source_type="industry_context",
            metadata={},
        )
        retrieval = RetrievalService(repo)
        scorer = RiskScorer()
        model = DeterministicModelProvider()

        # Client whose keywords have zero overlap with the event
        unrelated_client = Client(
            id="client-pharma-001",
            name="PharmaGen Ltd",
            industry="pharmaceuticals",
            geography=["south_asia"],
            keywords=["vaccine", "clinical_trial", "api_manufacturing"],
        )

        svc = AssessmentService(
            assessment_store=store,
            retrieval_service=retrieval,
            model_provider=model,
            risk_scorer=scorer,
            clients=[unrelated_client],
            projects=[],
        )

        # Event about cyber/banking — no overlap with pharma keywords
        event = _make_event()
        classification = _make_classification(event)

        result = await svc.assess_event(event, classification)

        assert result == []


class TestEmptyKnowledgeBase:

    async def test_assessment_succeeds_with_empty_evidence(self, store):
        repo = LexicalKnowledgeRepository()  # no documents indexed
        retrieval = RetrievalService(repo)
        scorer = RiskScorer()
        model = DeterministicModelProvider()

        client = _make_client()
        svc = AssessmentService(
            assessment_store=store,
            retrieval_service=retrieval,
            model_provider=model,
            risk_scorer=scorer,
            clients=[client],
            projects=[],
        )

        event = _make_event()
        classification = _make_classification(event)

        assessments = await svc.assess_event(event, classification)

        assert len(assessments) >= 1
        assert assessments[0].evidence_references == []


class TestModelValidationFailure:

    async def test_per_client_error_does_not_abort_event(self, store):
        """
        A model that always raises should cause zero assessments
        (the failing client's error is swallowed), not an exception.
        """

        class _BadModel(ModelProviderPort):
            @property
            def provider_name(self) -> str:
                return "bad_model"

            @property
            def model_version(self) -> str:
                return "0.0"

            async def generate(
                self,
                system_prompt: str,
                user_prompt: str,
                output_schema: Type[BaseModel],
                temperature: float = 0.3,
                max_tokens: int = 2048,
            ) -> BaseModel:
                # Trigger a ValidationError by validating bad data against AssessmentOutput
                AssessmentOutput.model_validate({"bad": "data"})
                raise RuntimeError("Should not reach here")  # pragma: no cover

            async def health_check(self) -> bool:
                return False

        repo = LexicalKnowledgeRepository()
        retrieval = RetrievalService(repo)
        scorer = RiskScorer()

        client = _make_client()
        svc = AssessmentService(
            assessment_store=store,
            retrieval_service=retrieval,
            model_provider=_BadModel(),
            risk_scorer=scorer,
            clients=[client],
            projects=[],
        )

        event = _make_event()
        classification = _make_classification(event)

        # Should NOT raise; should return empty list (client error is caught)
        result = await svc.assess_event(event, classification)
        assert result == []


class TestCitationValidation:

    async def test_bogus_reference_dropped_real_reference_kept(self):
        """
        RetrievalService.retrieve drops references whose source_document_id
        is not present in the repository index.
        """
        repo = LexicalKnowledgeRepository()
        await repo.index_document(
            document_id="real-doc-001",
            content="Cyber attack on banking infrastructure in Europe.",
            source_type="intelligence_report",
            metadata={"id": "real-doc-001"},
        )
        await repo.index_document(
            document_id="real-doc-002",
            content="Financial sanctions impact on investment banking operations.",
            source_type="industry_context",
            metadata={"id": "real-doc-002"},
        )

        retrieval = RetrievalService(repo)

        real_ref = EvidenceReference(
            source_document_id="real-doc-001",
            source_type="intelligence_report",
            content_excerpt="Cyber attack on banking infrastructure in Europe.",
            relevance_score=0.9,
            retrieval_strategy="lexical_bm25",
        )
        bogus_ref = EvidenceReference(
            source_document_id="nonexistent-doc-xyz",
            source_type="intelligence_report",
            content_excerpt="Some excerpt from a document that was never indexed.",
            relevance_score=0.8,
            retrieval_strategy="lexical_bm25",
        )

        client = _make_client()

        # Patch repo.search to return both real and bogus references
        async def _patched_search(query, top_k=5, source_types=None):
            return [real_ref, bogus_ref]

        original_search = repo.search
        repo.search = _patched_search
        try:
            refs = await retrieval.retrieve(
                query="cyber attack banking",
                client=client,
                correlation_id="test-correlation-id",
            )
        finally:
            repo.search = original_search

        returned_ids = {r.source_document_id for r in refs}
        assert "real-doc-001" in returned_ids, "Real reference should be kept"
        assert "nonexistent-doc-xyz" not in returned_ids, "Bogus reference should be dropped"
