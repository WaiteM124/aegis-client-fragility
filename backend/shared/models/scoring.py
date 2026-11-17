"""
Risk scoring data contracts.

The risk score is computed entirely by deterministic code in
``decision_engine.risk_scorer``.  An LLM never touches ``overall_score``
or ``risk_level``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .events import utcnow


class RiskLevel(str, Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskScore(BaseModel):
    """
    Deterministic risk score produced from classification severity,
    client exposure, and classification confidence.

    ``scoring_algorithm_version`` lets us re-score historical assessments
    when the algorithm changes without discarding the original evidence.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str
    event_id: str
    client_id: str
    project_id: Optional[str] = None

    # ── Component scores (0 – 100) ───────────────────────────────────────────
    overall_score: float = Field(ge=0.0, le=100.0)
    severity_component: float = Field(ge=0.0, le=100.0)
    exposure_component: float = Field(ge=0.0, le=100.0)
    confidence_component: float = Field(ge=0.0, le=100.0)

    risk_level: RiskLevel

    # ── Auditability ─────────────────────────────────────────────────────────
    scoring_algorithm_version: str
    factors: dict[str, float] = Field(
        default_factory=dict,
        description="Per-factor breakdown for transparency",
    )

    scored_at: datetime = Field(default_factory=utcnow)

    model_config = {"use_enum_values": True}
