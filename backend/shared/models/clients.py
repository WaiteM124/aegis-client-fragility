"""
Client and project data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .events import utcnow


class RiskProfile(str, Enum):  # noqa: UP042
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ProjectStatus(str, Enum):  # noqa: UP042
    ACTIVE = "active"
    PLANNED = "planned"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class Client(BaseModel):
    """
    A client whose interests Aegis monitors.

    ``keywords`` drives deterministic event-matching; ``geography`` drives
    region-based exposure scoring.  Neither field is ever passed to an LLM
    to decide relevance — that decision is made by the exposure scoring logic.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    industry: str
    geography: list[str] = Field(
        default_factory=list,
        description="Regions of operation used for exposure matching",
    )
    risk_profile: RiskProfile = RiskProfile.MODERATE
    keywords: list[str] = Field(
        default_factory=list,
        description="Domain keywords used for deterministic event matching",
    )
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    active: bool = True

    model_config = {"use_enum_values": True}


class Project(BaseModel):
    """An active engagement linked to a client."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    name: str
    description: str
    geography: list[str] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.ACTIVE
    keywords: list[str] = Field(default_factory=list)
    value_usd: float | None = Field(None, description="Approximate deal value in USD")
    created_at: datetime = Field(default_factory=utcnow)

    model_config = {"use_enum_values": True}


class ClientExposure(BaseModel):
    """
    Records that a client is potentially affected by an event.

    ``relevance_score`` is computed deterministically from keyword and
    geography matches — never assigned by an LLM.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    event_id: str
    project_id: str | None = None
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic score: fraction of matched keywords + geography",
    )
    matched_keywords: list[str] = Field(default_factory=list)
    matched_geography: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=utcnow)
