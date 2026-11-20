"""
Unit tests for client matching improvements (checkpoint 4).

Covers:
  - Word-boundary keyword matching (no substring false matches)
  - Geographic hierarchy normalisation
  - Synonym expansion via classifier tags
  - Multi-client geographic overlap
  - Conflicting signals (high severity + no geographic overlap)
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pytest

from backend.assessment.service import AssessmentService
from backend.decision_engine.risk_scorer import RiskScorer
from backend.event_processing.classifier import RuleBasedClassifier
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.persistence.sqlite.assessment_store import SQLiteAssessmentStore
from backend.retrieval.service import RetrievalService
from backend.shared.models.clients import Client
from backend.shared.models.events import Event, EventCategory, EventClassification, EventSeverity

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_event(**kwargs) -> Event:
    defaults = dict(
        source="test",
        title="Test event",
        raw_content="Test content.",
        event_date=datetime(2026, 11, 15),
        affected_regions=["europe"],
    )
    defaults.update(kwargs)
    return Event(**defaults)


def _make_classification(event: Event, **kwargs) -> EventClassification:
    defaults = dict(
        event_id=event.id,
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.MEDIUM,
        confidence=0.6,
        classifier_version="1.0",
    )
    defaults.update(kwargs)
    return EventClassification(**defaults)


@pytest.fixture
async def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = SQLiteAssessmentStore(path)
    await s.initialise()
    yield s
    await s.close()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _make_service(clients: list[Client], store) -> AssessmentService:
    repo = LexicalKnowledgeRepository()
    retrieval = RetrievalService(repo)
    return AssessmentService(
        assessment_store=store,
        retrieval_service=retrieval,
        model_provider=DeterministicModelProvider(),
        risk_scorer=RiskScorer(),
        clients=clients,
        projects=[],
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestNoSubstringFalseMatch:
    """Word-boundary check: 'oil' must not match 'soil', 'recoil', 'spoil'."""

    async def test_no_substring_false_match(self, store):
        # client has "oil" keyword; event text has "soil" and "recoil" but NOT standalone "oil"
        client = Client(
            id="client-oil-test",
            name="Oil Corp",
            industry="energy",
            geography=["asia_pacific"],  # event is in europe → no geo match either
            keywords=["oil", "gas"],
        )
        event = _make_event(
            title="Agricultural soil contamination crisis in farmlands",
            raw_content=(
                "Widespread soil contamination discovered across farmland regions. "
                "The recoil effect from chemical pesticide overuse continues. "
                "Toil of cleanup workers increases each year. "
                "Despoil of natural habitats threatens biodiversity."
            ),
            affected_regions=["europe"],
        )
        cls = _make_classification(event)
        svc = _make_service([client], store)

        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-oil-test" not in matched_ids, (
            "Word-boundary check must prevent 'soil'/'recoil' from matching keyword 'oil'"
        )


class TestGeographicHierarchy:
    """Events in sub-regions match clients registered in the parent region."""

    async def test_eastern_europe_matches_europe_client(self, store):
        client = Client(
            id="client-europe",
            name="European Bank",
            industry="investment_banking",
            geography=["europe"],
            keywords=["sanctions", "investment"],
        )
        event = _make_event(
            title="Sanctions imposed following eastern European conflict",
            raw_content=(
                "Major sanctions and investment restrictions announced following "
                "escalation in eastern European territory."
            ),
            affected_regions=["eastern_europe"],  # maps to 'europe' via hierarchy
        )
        cls = _make_classification(event)
        svc = _make_service([client], store)

        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-europe" in matched_ids, (
            "eastern_europe must match client in europe via geo hierarchy"
        )

    async def test_geographic_hierarchy_gulf(self, store):
        """Event in 'gulf' sub-region matches client registered in 'middle_east'."""
        client = Client(
            id="client-me-gulf",
            name="Gulf Energy Corp",
            industry="energy",
            geography=["middle_east"],
            keywords=["oil", "gas", "sanctions"],
        )
        event = _make_event(
            title="Oil pipeline disruption in Gulf region",
            raw_content=(
                "Major oil and gas pipeline disruptions in the Gulf region following "
                "escalating sanctions and geopolitical tensions."
            ),
            affected_regions=["gulf"],  # maps to 'middle_east' via hierarchy
        )
        cls = _make_classification(event)
        svc = _make_service([client], store)

        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-me-gulf" in matched_ids, (
            "gulf must match client in middle_east via geo hierarchy"
        )

    async def test_eastern_europe_does_not_match_middle_east_client(self, store):
        """Geographic hierarchy must NOT over-match unrelated regions."""
        client = Client(
            id="client-me",
            name="Middle East Corp",
            industry="energy",
            geography=["middle_east"],
            keywords=["oil", "gas"],  # appear in event text
        )
        event = _make_event(
            title="Oil and gas supply disrupted by eastern European conflict",
            raw_content=(
                "Major oil and gas pipeline disruptions following conflict in "
                "eastern European territory. Sanctions imposed on energy exports."
            ),
            affected_regions=["eastern_europe"],
        )
        cls = _make_classification(event)
        svc = _make_service([client], store)

        # client matches via keywords (oil, gas) but NOT via geography
        # (eastern_europe → europe ≠ middle_east)
        assessments = await svc.assess_event(event, cls)

        # client IS matched via keywords — verify matched_geography is empty
        for a in assessments:
            if a.client_id == "client-me":
                exposures = await store.list_exposures(a.event_id)
                for exp in exposures:
                    if exp.client_id == "client-me":
                        assert exp.matched_geography == [], (
                            "eastern_europe must NOT match middle_east via hierarchy"
                        )


class TestSynonymExpansion:
    """Events mentioning 'chip'/'chips' match clients with 'semiconductor' keyword."""

    async def test_synonym_expansion_chip_matches_semiconductor(self, store):
        client_005 = Client(
            id="client-005",
            name="Auriga Digital Infrastructure",
            industry="technology",
            geography=["europe", "north_america", "asia_pacific"],
            keywords=[
                "cloud", "data centre", "cyber", "infrastructure", "software",
                "ai", "semiconductor", "talent", "digital", "network", "security",
            ],
        )
        event = _make_event(
            title="Global chip shortage worsens amid supply constraints",
            raw_content=(
                "The ongoing chip shortage is severely impacting technology manufacturers. "
                "Microchip production cannot meet global demand. "
                "Major technology companies are reporting significant revenue impacts."
            ),
            affected_regions=["europe"],
        )

        # Classifier must expand 'chip'/'microchip' → 'semiconductor' in event.tags
        classifier = RuleBasedClassifier()
        cls = classifier.classify(event)

        svc = _make_service([client_005], store)
        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-005" in matched_ids, (
            "Synonym expansion: 'chip' → 'semiconductor' must match client-005's keyword"
        )

    async def test_synonym_ransomware_matches_cyber_client(self, store):
        client = Client(
            id="client-cyber",
            name="Tech Corp",
            industry="technology",
            geography=["europe"],
            keywords=["cyber", "network", "security"],
        )
        event = _make_event(
            title="Ransomware attack cripples hospital network",
            raw_content=(
                "A ransomware attack has compromised hospital network systems. "
                "Patient data at risk. Malware spreading across connected devices."
            ),
            affected_regions=["europe"],
        )

        classifier = RuleBasedClassifier()
        cls = classifier.classify(event)

        svc = _make_service([client], store)
        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-cyber" in matched_ids, (
            "Synonym expansion: 'ransomware'/'malware' → 'cyber' must match cyber keyword"
        )


class TestOverlappingGeographyMultipleClients:
    """An event affecting multiple regions correctly matches all relevant clients."""

    async def test_europe_and_asia_pacific_event_matches_both_clients(self, store):
        client_eu = Client(
            id="client-eu",
            name="European Corp",
            industry="manufacturing",
            geography=["europe"],
            keywords=["supply chain", "trade"],
        )
        client_ap = Client(
            id="client-ap",
            name="Asia Pacific Corp",
            industry="manufacturing",
            geography=["asia_pacific"],
            keywords=["supply chain", "trade"],
        )
        event = _make_event(
            title="Supply chain trade disruption affects Europe and Asia Pacific",
            raw_content=(
                "Major supply chain disruption impacts manufacturing operations in "
                "both Europe and Asia Pacific regions. Trade volumes declining sharply."
            ),
            affected_regions=["europe", "asia_pacific"],
        )
        cls = _make_classification(event)
        svc = _make_service([client_eu, client_ap], store)

        assessments = await svc.assess_event(event, cls)

        matched_ids = {a.client_id for a in assessments}
        assert "client-eu" in matched_ids, "Europe client must match event affecting europe"
        assert "client-ap" in matched_ids, "Asia Pacific client must match event in asia_pacific"


class TestConflictingSignalsLowScore:
    """
    High severity event with zero geographic overlap and zero keyword overlap
    produces no risk score (effectively 0 < 30).
    """

    async def test_conflicting_signals_low_score(self, store):
        # Client monitors technology/semiconductor in asia_pacific
        client = Client(
            id="client-conflict",
            name="Remote Region Investor",
            industry="investment_banking",
            geography=["asia_pacific"],
            keywords=["semiconductor", "cloud", "digital"],
        )
        # High-severity event in a region unrelated to the client,
        # with content that doesn't match client keywords.
        event = _make_event(
            title="Severe armed conflict erupts in remote territory",
            raw_content=(
                "Major armed conflict has erupted. Serious military operations underway. "
                "Significant civilian displacement reported. Emergency response activated. "
                "Widespread infrastructure disruption expected."
            ),
            affected_regions=["latin_america"],  # → north_america via hierarchy, not asia_pacific
        )
        cls = EventClassification(
            event_id=event.id,
            category=EventCategory.GEOPOLITICAL,
            severity=EventSeverity.HIGH,
            confidence=0.75,
            classifier_version="1.0",
        )
        svc = _make_service([client], store)

        assessments = await svc.assess_event(event, cls)

        # Collect any risk scores produced
        scores = []
        for a in assessments:
            score = await store.get_risk_score(a.id)
            if score:
                scores.append(score.overall_score)

        # Either no match (empty list) or all scores < 30
        assert all(s < 30 for s in scores), (
            f"High severity + zero geo overlap must yield risk score < 30; got {scores}"
        )
        # In practice this should produce no assessments since:
        # - latin_america → north_america (not asia_pacific) → no geo match
        # - 'semiconductor', 'cloud', 'digital' don't appear in event text → no kw match
        assert assessments == [], (
            "Zero geographic and keyword overlap must produce no assessments"
        )
