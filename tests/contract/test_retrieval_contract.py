"""
Contract tests for RetrievalService / RetrievalResult.

Verifies:
  1. retrieved_ids always equals {r.source_document_id for r in references}.
  2. A reference fabricated by a hypothetical live LLM (not in retrieved set)
     is stripped by the assessment service's citation guard.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.assessment.service import AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.retrieval.service import RetrievalResult, RetrievalService
from backend.shared.models.assessment import EvidenceReference
from backend.shared.models.clients import Client
from backend.shared.models.events import Event, EventCategory, EventClassification, EventSeverity


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def repo():
    r = LexicalKnowledgeRepository()
    await r.index_document(
        document_id="real-doc-001",
        content="Cyber attack on banking infrastructure in Europe. Financial sanctions impact.",
        source_type="intelligence_report",
        metadata={"id": "real-doc-001"},
    )
    await r.index_document(
        document_id="real-doc-002",
        content="Financial markets disruption from geopolitical tensions. Investment banking risk.",
        source_type="industry_context",
        metadata={"id": "real-doc-002"},
    )
    return r


@pytest.fixture
def client():
    return Client(
        id="client-001",
        name="Test Bank",
        industry="investment_banking",
        geography=["europe"],
        keywords=["cyber", "financial", "banking", "sanctions"],
    )


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


# ── Contract tests ────────────────────────────────────────────────────────────


class TestRetrievalContract:

    async def test_retrieved_ids_match_returned_references(self, repo, client):
        """
        retrieved_ids must be exactly the set of source_document_ids
        in the returned references list — no more, no less.
        """
        retrieval = RetrievalService(repo)
        result = await retrieval.retrieve(
            query="cyber attack financial banking europe",
            client=client,
        )
        assert isinstance(result, RetrievalResult)
        expected_ids = {r.source_document_id for r in result.references}
        assert result.retrieved_ids == expected_ids

    async def test_retrieved_ids_is_frozenset(self, repo, client):
        retrieval = RetrievalService(repo)
        result = await retrieval.retrieve(
            query="cyber attack banking",
            client=client,
        )
        assert isinstance(result.retrieved_ids, frozenset)

    async def test_empty_repo_returns_empty_result(self, client):
        empty_repo = LexicalKnowledgeRepository()
        retrieval = RetrievalService(empty_repo)
        result = await retrieval.retrieve(query="anything", client=client)
        assert result.references == []
        assert result.retrieved_ids == frozenset()

    async def test_fabricated_id_rejected(self, repo, client, store):
        """
        When a reference with a valid-index ID that was NOT in the retrieved
        set is injected, the assessment service's citation guard drops it.

        This simulates a live LLM hallucinating a document ID.
        """
        retrieval = RetrievalService(repo)

        # Patch BM25 search to return only 1 real reference
        real_ref = EvidenceReference(
            source_document_id="real-doc-001",
            source_type="intelligence_report",
            content_excerpt="Cyber attack on banking infrastructure in Europe.",
            relevance_score=0.9,
            retrieval_strategy="lexical_bm25",
        )

        async def _single_result(query, top_k=5, source_types=None):
            return [real_ref]

        original_search = repo.search
        repo.search = _single_result
        try:
            result = await retrieval.retrieve(
                query="cyber attack banking",
                client=client,
            )
        finally:
            repo.search = original_search

        # Only real-doc-001 should be in retrieved set
        assert result.retrieved_ids == {"real-doc-001"}
        assert len(result.references) == 1

        # Now test the assessment service guard: inject a second reference
        # with a valid-index ID (real-doc-002) that was NOT retrieved.
        fabricated_ref = EvidenceReference(
            source_document_id="real-doc-002",  # exists in index but NOT retrieved
            source_type="intelligence_report",
            content_excerpt="Fabricated content not from actual retrieval.",
            relevance_score=0.95,
            retrieval_strategy="lexical_bm25",
        )

        # Patch retrieve() to return the fabricated reference in the list
        # but with retrieved_ids containing only the real doc.
        async def _patched_retrieve(*args, **kwargs):
            return RetrievalResult(
                references=[real_ref, fabricated_ref],
                retrieved_ids=frozenset({"real-doc-001"}),
            )

        event = _make_event()
        classification = _make_classification(event)

        svc = AssessmentService(
            assessment_store=store,
            retrieval_service=retrieval,
            model_provider=DeterministicModelProvider(),
            risk_scorer=RiskScorer(),
            clients=[client],
            projects=[],
        )

        original_retrieve = retrieval.retrieve
        retrieval.retrieve = _patched_retrieve
        try:
            assessments = await svc.assess_event(event, classification)
        finally:
            retrieval.retrieve = original_retrieve

        assert len(assessments) == 1
        evidence_ids = {r.source_document_id for r in assessments[0].evidence_references}
        assert "real-doc-001" in evidence_ids, "Real retrieved reference should be kept"
        assert "real-doc-002" not in evidence_ids, (
            "Fabricated reference (not in retrieved_ids) must be stripped"
        )
