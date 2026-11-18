"""Port: event and classification persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models.events import Event, EventClassification


class EventStorePort(ABC):
    """
    Abstract persistence layer for events and their classifications.
    Concrete adapters: SQLiteEventStore (local), FirestoreEventStore (GCP).
    """

    @abstractmethod
    async def save_event(self, event: Event) -> None:
        """Upsert an event.  Called both on initial ingest and on status updates."""
        ...

    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[Event]:
        ...

    @abstractmethod
    async def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[Event]:
        ...

    @abstractmethod
    async def event_exists(self, idempotency_key: str) -> bool:
        """Return True if any event with this idempotency_key is already stored."""
        ...

    @abstractmethod
    async def update_event_status(self, event_id: str, status) -> None:
        """Fast path: update only the status field without loading the full record."""
        ...

    @abstractmethod
    async def save_classification(self, classification: EventClassification) -> None:
        ...

    @abstractmethod
    async def get_classification(self, event_id: str) -> Optional[EventClassification]:
        ...

    # ── Aggregation ───────────────────────────────────────────────────────────

    async def get_events_summary(self) -> dict:
        """Return counts by status and by severity (from joined classifications).

        Return shape: {"total": int, "by_status": {str: int}, "by_severity": {str: int}}
        """
        return {"total": 0, "by_status": {}, "by_severity": {}}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialise(self) -> None:
        """Create tables / indexes.  Called once at startup."""

    async def close(self) -> None:
        """Release connections."""
