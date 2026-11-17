"""Typed errors for the assessment service."""

from __future__ import annotations


class AssessmentError(Exception):
    """Raised when an impact assessment cannot be produced."""

    def __init__(self, event_id: str, reason: str, cause: Exception | None = None):
        super().__init__(f"Assessment failed for event {event_id}: {reason}")
        self.event_id = event_id
        self.reason = reason
        self.cause = cause
