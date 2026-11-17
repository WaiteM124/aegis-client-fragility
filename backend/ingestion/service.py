"""
Event ingestion service.

Responsibilities:
  - Validate the inbound event payload (delegated to Pydantic).
  - Enforce idempotency via a caller-supplied key.
  - Persist the raw event.
  - Publish it to the message bus so the worker can process it
    independently and asynchronously.

The ingestion service does NOT normalise, classify, or assess events.
It is a thin write-and-publish layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..shared.config import get_settings
from ..shared.logging import get_logger
from ..shared.models.events import Event, EventStatus
from ..shared.ports.event_store import EventStorePort
from ..shared.ports.message_bus import MessageBusPort

logger = get_logger("ingestion")


class DuplicateEventError(Exception):
    """Raised when a submission with a known idempotency_key is received."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"Event already ingested: idempotency_key={idempotency_key!r}")


class IngestionService:
    def __init__(
        self,
        event_store: EventStorePort,
        message_bus: MessageBusPort,
    ) -> None:
        self._event_store = event_store
        self._message_bus = message_bus
        self._settings = get_settings()

    async def ingest_event(
        self,
        source: str,
        title: str,
        raw_content: str,
        event_date: datetime,
        source_url: Optional[str] = None,
        location: Optional[str] = None,
        affected_regions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Event:
        """
        Persist and publish a new global event.

        Returns the created Event immediately (202 Accepted semantics).
        All downstream processing happens asynchronously via the worker.

        Raises DuplicateEventError if ``idempotency_key`` is already known.
        """
        if idempotency_key:
            exists = await self._event_store.event_exists(idempotency_key)
            if exists:
                logger.info(
                    "Duplicate event suppressed",
                    extra={"idempotency_key": idempotency_key},
                )
                raise DuplicateEventError(idempotency_key)

        event = Event(
            source=source,
            source_url=source_url,
            title=title,
            raw_content=raw_content,
            event_date=event_date,
            location=location,
            affected_regions=affected_regions or [],
            tags=tags or [],
            idempotency_key=idempotency_key,
            status=EventStatus.PENDING,
        )

        logger.info(
            "Ingesting event",
            extra={
                "event_id": event.id,
                "correlation_id": event.correlation_id,
                "source": source,
                "title": title[:80],
            },
        )

        await self._event_store.save_event(event)

        message_id = await self._message_bus.publish(
            topic=self._settings.events_topic,
            message=event.model_dump(mode="json"),
            correlation_id=event.correlation_id,
            attributes={"source": source, "event_type": "raw_event"},
        )

        logger.info(
            "Event published to bus",
            extra={
                "event_id": event.id,
                "correlation_id": event.correlation_id,
                "message_id": message_id,
                "topic": self._settings.events_topic,
            },
        )

        return event
