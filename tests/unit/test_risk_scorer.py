"""
Unit tests for the deterministic risk scorer.

The scorer is a pure function: given the same inputs it must always
produce the same score.  No I/O, no randomness.
"""

import pytest
from datetime import datetime

from backend.decision_engine.risk_scorer import RiskScorer, _classify_level, VERSION
from backend.shared.models.assessment import ImpactAssessment
from backend.shared.models.clients import ClientExposure
from backend.shared.models.events import EventClassification, EventCategory, EventSeverity
from backend.shared.models.scoring import RiskLevel


def _make_classification(severity: str, confidence: float = 0.8) -> EventClassification:
    return EventClassification(
        event_id="e1",
        category=EventCategory.GEOPOLITICAL,
        severity=severity,
        confidence=confidence,
        classifier_version=VERSION,
    )


def _make_exposure(relevance: float) -> ClientExposure:
    return ClientExposure(
        client_id="c1",
        event_id="e1",
        relevance_score=relevance,
    )


def _make_assessment() -> ImpactAssessment:
    return ImpactAssessment(
        event_id="e1",
        client_id="c1",
        correlation_id="corr-1",
        assessment_text="Test assessment.",
        model_provider="deterministic",
        model_version="rules-v1",
        raw_model_output={},
    )


class TestRiskScorer:
    scorer = RiskScorer()

    def test_critical_severity_produces_high_score(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("critical", confidence=0.9),
            exposure=_make_exposure(0.8),
        )
        assert score.overall_score >= 70.0

    def test_low_severity_low_exposure_produces_low_score(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("low", confidence=0.4),
            exposure=_make_exposure(0.1),
        )
        assert score.overall_score < 40.0

    def test_score_is_deterministic(self):
        cls = _make_classification("high", confidence=0.75)
        exp = _make_exposure(0.5)
        a = _make_assessment()
        score1 = self.scorer.score(a, cls, exp)
        score2 = self.scorer.score(a, cls, exp)
        assert score1.overall_score == score2.overall_score

    def test_score_clamped_to_100(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("critical", confidence=1.0),
            exposure=_make_exposure(1.0),
        )
        assert 0.0 <= score.overall_score <= 100.0

    def test_algorithm_version_recorded(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("high"),
            exposure=_make_exposure(0.5),
        )
        assert score.scoring_algorithm_version == VERSION

    def test_risk_level_matches_score(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("critical", confidence=1.0),
            exposure=_make_exposure(1.0),
        )
        # critical severity (100) × 0.5 + exposure (100) × 0.35 + confidence (100) × 0.15 = 100
        assert score.risk_level == RiskLevel.CRITICAL

    def test_factors_recorded(self):
        score = self.scorer.score(
            assessment=_make_assessment(),
            classification=_make_classification("high"),
            exposure=_make_exposure(0.6),
        )
        assert "severity_weight" in score.factors
        assert "exposure_weight" in score.factors


class TestClassifyLevel:
    def test_thresholds(self):
        assert _classify_level(85.0) == RiskLevel.CRITICAL
        assert _classify_level(65.0) == RiskLevel.HIGH
        assert _classify_level(50.0) == RiskLevel.MODERATE
        assert _classify_level(30.0) == RiskLevel.LOW
        assert _classify_level(10.0) == RiskLevel.MINIMAL
