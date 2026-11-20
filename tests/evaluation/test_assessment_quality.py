"""
Evaluation tests: assessment quality baselines.

These tests assert behavioural properties of the pipeline on known
synthetic inputs — a lightweight evaluation harness that can be extended
with real model providers in later checkpoints.

Unlike unit/integration tests, evaluation tests are allowed to be slow
and may be excluded from CI with:  pytest -m "not evaluation"
"""

from datetime import datetime

import pytest

from backend.decision_engine.risk_scorer import RiskScorer
from backend.event_processing.classifier import RuleBasedClassifier
from backend.event_processing.normaliser import EventNormaliser
from backend.shared.models.clients import ClientExposure
from backend.shared.models.events import Event

pytestmark = pytest.mark.evaluation


GEOPOLITICAL_EVENT = Event(
    source="test",
    title="Armed conflict erupts at contested border; military invasion launched",
    raw_content=(
        "Full-scale military invasion has been launched across the contested border. "
        "Sanctions are expected; oil infrastructure is at risk. War declared. "
        "Critical infrastructure attacks reported."
    ),
    event_date=datetime(2026, 11, 15),
    affected_regions=["europe", "middle_east"],
)

CYBER_EVENT = Event(
    source="test",
    title="Ransomware attack cripples major bank network",
    raw_content=(
        "A sophisticated ransomware cyberattack has taken down the core banking "
        "systems of a major European financial institution. Data breach suspected. "
        "Malware has spread to subsidiary networks."
    ),
    event_date=datetime(2026, 11, 10),
    affected_regions=["europe"],
)


class TestClassifierQuality:
    clf = RuleBasedClassifier()
    norm = EventNormaliser()

    def test_geopolitical_event_classified_correctly(self):
        event = self.norm.normalise(GEOPOLITICAL_EVENT)
        cls = self.clf.classify(event)
        assert cls.category == "geopolitical"
        assert cls.severity in ("critical", "high")
        assert cls.confidence >= 0.5

    def test_cyber_event_classified_correctly(self):
        event = self.norm.normalise(CYBER_EVENT)
        cls = self.clf.classify(event)
        assert cls.category == "cyber"
        assert cls.severity in ("critical", "high")


class TestScorerQuality:
    clf = RuleBasedClassifier()
    norm = EventNormaliser()
    scorer = RiskScorer()

    def test_geopolitical_critical_produces_high_risk(self):
        event = self.norm.normalise(GEOPOLITICAL_EVENT)
        cls = self.clf.classify(event)
        from backend.shared.models.assessment import ImpactAssessment
        assessment = ImpactAssessment(
            event_id=event.id,
            client_id="c1",
            correlation_id=event.correlation_id,
            assessment_text="Test.",
            model_provider="deterministic",
            model_version="rules-v1",
            raw_model_output={},
        )
        exposure = ClientExposure(
            client_id="c1",
            event_id=event.id,
            relevance_score=0.7,
        )
        score = self.scorer.score(assessment, cls, exposure)
        assert score.risk_level in ("high", "critical")
        assert score.overall_score >= 50.0
