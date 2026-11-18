"""SQLite adapter for EventStorePort."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

import aiosqlite

from ...shared.logging import get_logger
from ...shared.models.events import Event, EventClassification, EventStatus
from ...shared.ports.event_store import EventStorePort

logger = get_logger("persistence.sqlite.events")

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_url      TEXT,
    title           TEXT NOT NULL,
    raw_content     TEXT NOT NULL,
    summary         TEXT,
    event_date      TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    location        TEXT,
    affected_regions TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'pending',
    correlation_id  TEXT NOT NULL,
    idempotency_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS event_classifications (
    id                  TEXT PRIMARY KEY,
    event_id            TEXT NOT NULL REFERENCES events(id),
    category            TEXT NOT NULL,
    severity            TEXT NOT NULL,
    confidence          REAL NOT NULL,
    sub_categories      TEXT NOT NULL DEFAULT '[]',
    classified_at       TEXT NOT NULL,
    classifier_version  TEXT NOT NULL,
    rationale           TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_status
    ON events(status);

CREATE INDEX IF NOT EXISTS idx_events_idempotency
    ON events(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_classifications_event
    ON event_classifications(event_id);
"""


class SQLiteEventStore(EventStorePort):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialise(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        # Execute DDL statements individually (executescript closes transaction)
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._db.execute(stmt)
        await self._db.commit()
        logger.info("SQLite event store initialised", extra={"db_path": self._db_path})

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ── EventStorePort ────────────────────────────────────────────────────────

    async def save_event(self, event: Event) -> None:
        await self._db.execute(
            """
            INSERT INTO events (
                id, source, source_url, title, raw_content, summary,
                event_date, ingested_at, location, affected_regions,
                tags, status, correlation_id, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status          = excluded.status,
                summary         = excluded.summary,
                affected_regions = excluded.affected_regions
            """,
            (
                event.id,
                event.source,
                event.source_url,
                event.title,
                event.raw_content,
                event.summary,
                event.event_date.isoformat(),
                event.ingested_at.isoformat(),
                event.location,
                json.dumps(event.affected_regions),
                json.dumps(event.tags),
                str(event.status),
                event.correlation_id,
                event.idempotency_key,
            ),
        )
        await self._db.commit()

    async def get_event(self, event_id: str) -> Optional[Event]:
        async with self._db.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_event(row) if row else None

    async def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[Event]:
        if status:
            sql = (
                "SELECT * FROM events WHERE status = ? "
                "ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
            )
            params = (status, limit, offset)
        else:
            sql = "SELECT * FROM events ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_event(r) for r in rows]

    async def event_exists(self, idempotency_key: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM events WHERE idempotency_key = ?", (idempotency_key,)
        ) as cur:
            return await cur.fetchone() is not None

    async def update_event_status(self, event_id: str, status) -> None:
        value = status.value if hasattr(status, "value") else str(status)
        await self._db.execute(
            "UPDATE events SET status = ? WHERE id = ?", (value, event_id)
        )
        await self._db.commit()

    async def save_classification(self, classification: EventClassification) -> None:
        await self._db.execute(
            """
            INSERT INTO event_classifications (
                id, event_id, category, severity, confidence,
                sub_categories, classified_at, classifier_version, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                classification.id,
                classification.event_id,
                str(classification.category),
                str(classification.severity),
                classification.confidence,
                json.dumps(classification.sub_categories),
                classification.classified_at.isoformat(),
                classification.classifier_version,
                classification.rationale,
            ),
        )
        await self._db.commit()

    async def get_classification(self, event_id: str) -> Optional[EventClassification]:
        async with self._db.execute(
            """
            SELECT * FROM event_classifications
            WHERE event_id = ?
            ORDER BY classified_at DESC LIMIT 1
            """,
            (event_id,),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_classification(row) if row else None

    async def get_events_summary(self) -> dict:
        """Return counts by status and by severity (from joined classifications)."""
        # Total and by-status counts
        async with self._db.execute("SELECT status, COUNT(*) as cnt FROM events GROUP BY status") as cur:
            rows = await cur.fetchall()
        by_status = {row["status"]: row["cnt"] for row in rows}
        total = sum(by_status.values())

        # By-severity: use the most recent classification per event
        async with self._db.execute(
            """
            SELECT ec.severity, COUNT(DISTINCT ec.event_id) as cnt
            FROM event_classifications ec
            WHERE ec.id = (
                SELECT id FROM event_classifications ec2
                WHERE ec2.event_id = ec.event_id
                ORDER BY ec2.classified_at DESC LIMIT 1
            )
            GROUP BY ec.severity
            """
        ) as cur:
            rows = await cur.fetchall()
        by_severity = {row["severity"]: row["cnt"] for row in rows}

        return {"total": total, "by_status": by_status, "by_severity": by_severity}


# ── Row mappers ───────────────────────────────────────────────────────────────


def _row_to_event(row) -> Event:
    return Event(
        id=row["id"],
        source=row["source"],
        source_url=row["source_url"],
        title=row["title"],
        raw_content=row["raw_content"],
        summary=row["summary"],
        event_date=datetime.fromisoformat(row["event_date"]),
        ingested_at=datetime.fromisoformat(row["ingested_at"]),
        location=row["location"],
        affected_regions=json.loads(row["affected_regions"]),
        tags=json.loads(row["tags"]),
        status=row["status"],
        correlation_id=row["correlation_id"],
        idempotency_key=row["idempotency_key"],
    )


def _row_to_classification(row) -> EventClassification:
    return EventClassification(
        id=row["id"],
        event_id=row["event_id"],
        category=row["category"],
        severity=row["severity"],
        confidence=row["confidence"],
        sub_categories=json.loads(row["sub_categories"]),
        classified_at=datetime.fromisoformat(row["classified_at"]),
        classifier_version=row["classifier_version"],
        rationale=row["rationale"],
    )
