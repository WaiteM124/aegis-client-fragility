"""
Firestore adapter for EventStorePort.

Accepts an injected Firestore client so the emulator can be used in tests
without touching any live GCP project.

Usage (emulator):
    import os
    os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8086"
    from google.cloud import firestore
    db = firestore.Client(project="aegis-local")
    store = FirestoreEventStore(db)
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from ...shared.logging import get_logger
from ...shared.models.events import Event, EventClassification
from ...shared.ports.event_store import EventStorePort

logger = get_logger("persistence.firestore.events")

_EVENTS = "aegis_events"
_CLASSIFICATIONS = "aegis_classifications"


class FirestoreEventStore(EventStorePort):
    """
    Firestore-backed event store.

    ``db`` is an injected ``google.cloud.firestore.Client`` (synchronous).
    All blocking Firestore calls are offloaded with ``asyncio.to_thread``.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialise(self) -> None:
        """No-op for Firestore — collections are created on first write."""

    async def close(self) -> None:
        """No-op — connection lifecycle is managed by the caller."""

    # ── EventStorePort ────────────────────────────────────────────────────────

    async def save_event(self, event: Event) -> None:
        data = _event_to_dict(event)
        doc_ref = self._db.collection(_EVENTS).document(event.id)
        await asyncio.to_thread(doc_ref.set, data)

    async def get_event(self, event_id: str) -> Event | None:
        doc_ref = self._db.collection(_EVENTS).document(event_id)
        snap = await asyncio.to_thread(doc_ref.get)
        if not snap.exists:
            return None
        return _dict_to_event(snap.to_dict())

    async def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Event]:
        def _query():
            col = self._db.collection(_EVENTS)
            q = col.order_by("ingested_at", direction="DESCENDING")
            if status:
                q = col.where("status", "==", status).order_by(
                    "ingested_at", direction="DESCENDING"
                )
            # Firestore doesn't have SQL-style offset; use limit only for now
            return list(q.limit(limit).stream())

        snaps = await asyncio.to_thread(_query)
        events = [_dict_to_event(s.to_dict()) for s in snaps]
        return events[offset:] if offset else events

    async def event_exists(self, idempotency_key: str) -> bool:
        def _check():
            col = self._db.collection(_EVENTS)
            docs = list(
                col.where("idempotency_key", "==", idempotency_key).limit(1).stream()
            )
            return len(docs) > 0

        return await asyncio.to_thread(_check)

    async def update_event_status(self, event_id: str, status) -> None:
        value = status.value if hasattr(status, "value") else str(status)
        doc_ref = self._db.collection(_EVENTS).document(event_id)
        await asyncio.to_thread(doc_ref.update, {"status": value})

    async def save_classification(self, classification: EventClassification) -> None:
        data = _classification_to_dict(classification)
        # Key by classification id for idempotency
        doc_ref = self._db.collection(_CLASSIFICATIONS).document(classification.id)
        await asyncio.to_thread(doc_ref.set, data)

    async def get_classification(self, event_id: str) -> EventClassification | None:
        def _query():
            return list(
                self._db.collection(_CLASSIFICATIONS)
                .where("event_id", "==", event_id)
                .order_by("classified_at", direction="DESCENDING")
                .limit(1)
                .stream()
            )

        snaps = await asyncio.to_thread(_query)
        if not snaps:
            return None
        return _dict_to_classification(snaps[0].to_dict())

    async def get_events_summary(self) -> dict:
        """Return counts by status and by severity."""

        def _fetch():
            events = list(self._db.collection(_EVENTS).stream())
            classifications = list(self._db.collection(_CLASSIFICATIONS).stream())
            return events, classifications

        event_snaps, cls_snaps = await asyncio.to_thread(_fetch)

        by_status: dict[str, int] = {}
        for snap in event_snaps:
            d = snap.to_dict()
            s = d.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        # Latest classification per event for severity
        latest_cls: dict[str, dict] = {}
        for snap in cls_snaps:
            d = snap.to_dict()
            eid = d.get("event_id", "")
            if eid not in latest_cls or d.get("classified_at", "") > latest_cls[eid].get(
                "classified_at", ""
            ):
                latest_cls[eid] = d

        by_severity: dict[str, int] = {}
        for d in latest_cls.values():
            sev = d.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total": len(event_snaps),
            "by_status": by_status,
            "by_severity": by_severity,
        }


# ── Serialisers ───────────────────────────────────────────────────────────────


def _event_to_dict(event: Event) -> dict:
    return {
        "id": event.id,
        "source": event.source,
        "source_url": event.source_url,
        "title": event.title,
        "raw_content": event.raw_content,
        "summary": event.summary,
        "event_date": event.event_date.isoformat(),
        "ingested_at": event.ingested_at.isoformat(),
        "location": event.location,
        "affected_regions": event.affected_regions,
        "tags": event.tags,
        "status": str(event.status),
        "correlation_id": event.correlation_id,
        "idempotency_key": event.idempotency_key,
    }


def _dict_to_event(d: dict) -> Event:
    return Event(
        id=d["id"],
        source=d["source"],
        source_url=d.get("source_url"),
        title=d["title"],
        raw_content=d["raw_content"],
        summary=d.get("summary"),
        event_date=datetime.fromisoformat(d["event_date"]),
        ingested_at=datetime.fromisoformat(d["ingested_at"]),
        location=d.get("location"),
        affected_regions=d.get("affected_regions", []),
        tags=d.get("tags", []),
        status=d.get("status", "pending"),
        correlation_id=d.get("correlation_id", ""),
        idempotency_key=d.get("idempotency_key"),
    )


def _classification_to_dict(cls: EventClassification) -> dict:
    return {
        "id": cls.id,
        "event_id": cls.event_id,
        "category": str(cls.category),
        "severity": str(cls.severity),
        "confidence": cls.confidence,
        "sub_categories": cls.sub_categories,
        "classified_at": cls.classified_at.isoformat(),
        "classifier_version": cls.classifier_version,
        "rationale": cls.rationale,
    }


def _dict_to_classification(d: dict) -> EventClassification:
    return EventClassification(
        id=d["id"],
        event_id=d["event_id"],
        category=d["category"],
        severity=d["severity"],
        confidence=d["confidence"],
        sub_categories=d.get("sub_categories", []),
        classified_at=datetime.fromisoformat(d["classified_at"]),
        classifier_version=d["classifier_version"],
        rationale=d.get("rationale"),
    )
