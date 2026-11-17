"""
Deterministic risk scorer.

The score is computed entirely from:
  - EventClassification.severity  (from the rule-based classifier)
  - ClientExposure.relevance_score (from keyword/geography matching)
  - EventClassification.confidence (from the rule-based classifier)

No LLM output influences the numeric score or the risk level.
The model's assessment text is informational only.

Scoring algorithm v1.0.0:
  overall = severity_score × 0.50
          + exposure_score × 0.35
          + confidence_score × 0.15

  Where each component is in [0, 100].

  Risk levels:
    80–100 → CRITICAL
    60–79  → HIGH
    40–59  → MODERATE
    20–39  → LOW
    0–19   → MINIMAL
"""

from __future__ import annotations

from ..shared.logging import get_logger
from ..shared.models.assessment import ImpactAssessment
from ..shared.models.clients import ClientExposure
from ..shared.models.events import EventClassification
from ..shared.models.scoring import RiskLevel, RiskScore

logger = get_logger("risk_scorer")

VERSION = "1.0.0"

_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 100.0,
    "high": 75.0,
    "medium": 50.0,
    "low": 25.0,
}

_RISK_THRESHOLDS: list[tuple[float, RiskLevel]] = [
    (80.0, RiskLevel.CRITICAL),
    (60.0, RiskLevel.HIGH),
    (40.0, RiskLevel.MODERATE),
    (20.0, RiskLevel.LOW),
    (0.0, RiskLevel.MINIMAL),
]


class RiskScorer:
    def score(
        self,
        assessment: ImpactAssessment,
        classification: EventClassification,
        exposure: ClientExposure,
    ) -> RiskScore:
        severity_score = _SEVERITY_WEIGHTS.get(str(classification.severity).lower(), 25.0)
        exposure_score = round(exposure.relevance_score * 100.0, 2)
        confidence_score = round(classification.confidence * 100.0, 2)

        raw = (
            severity_score * 0.50
            + exposure_score * 0.35
            + confidence_score * 0.15
        )
        overall = round(min(max(raw, 0.0), 100.0), 2)
        risk_level = _classify_level(overall)

        score = RiskScore(
            assessment_id=assessment.id,
            event_id=assessment.event_id,
            client_id=assessment.client_id,
            project_id=assessment.project_id,
            overall_score=overall,
            severity_component=severity_score,
            exposure_component=exposure_score,
            confidence_component=confidence_score,
            risk_level=risk_level,
            scoring_algorithm_version=VERSION,
            factors={
                "severity_weight": severity_score,
                "severity_multiplier": 0.50,
                "exposure_weight": exposure_score,
                "exposure_multiplier": 0.35,
                "confidence_weight": confidence_score,
                "confidence_multiplier": 0.15,
            },
        )

        logger.info(
            "Risk score computed",
            extra={
                "assessment_id": assessment.id,
                "event_id": assessment.event_id,
                "client_id": assessment.client_id,
                "overall_score": overall,
                "risk_level": risk_level,
            },
        )

        return score


def _classify_level(score: float) -> RiskLevel:
    for threshold, level in _RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.MINIMAL
