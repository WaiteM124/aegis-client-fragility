"""
Event data contracts.

All timestamps are naive UTC datetimes. The utcnow() helper is used
everywhere inside Aegis so the convention is centralised.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return the current time in UTC as a naive datetime (timezone-stripped for SQLite)."""
    return datetime.now(UTC).replace(tzinfo=None)


class EventStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    NORMALISED = "normalised"
    CLASSIFIED = "classified"
    PUBLISHED = "published"
    PROCESSING = "processing"
    ASSESSED = "assessed"
    FAILED = "failed"


class EventSeverity(str, Enum):  # noqa: UP042
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventCategory(str, Enum):  # noqa: UP042
    GEOPOLITICAL = "geopolitical"
    ECONOMIC = "economic"
    NATURAL_DISASTER = "natural_disaster"
    CYBER = "cyber"
    REGULATORY = "regulatory"
    HEALTH = "health"
    SECURITY = "security"
    ENVIRONMENTAL = "environmental"
    SOCIAL = "social"
    TECHNOLOGY = "technology"
    UNKNOWN = "unknown"


class Event(BaseModel):
    """
    A normalised, source-agnostic record of a global event.

    ``idempotency_key`` is an optional caller-supplied value used to deduplicate
    submissions from external sources.  It is stored and checked before any
    processing begins.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = Field(description="Data source identifier, e.g. reuters, ap, manual")
    source_url: str | None = None
    title: str
    raw_content: str
    summary: str | None = None
    event_date: datetime
    ingested_at: datetime = Field(default_factory=utcnow)
    location: str | None = None
    affected_regions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: EventStatus = EventStatus.PENDING
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Propagated through every processing step for traceability",
    )
    idempotency_key: str | None = Field(
        None,
        description="Caller-supplied unique key; duplicate submissions are rejected with 409",
    )

    model_config = {"use_enum_values": True}


class EventClassification(BaseModel):
    """
    Deterministic classification produced by the rule-based classifier.
    No LLM involvement.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    category: EventCategory
    severity: EventSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    sub_categories: list[str] = Field(default_factory=list)
    classified_at: datetime = Field(default_factory=utcnow)
    classifier_version: str
    rationale: str | None = None

    model_config = {"use_enum_values": True}
