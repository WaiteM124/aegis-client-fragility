"""SQLite adapter for AssessmentStorePort."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import aiosqlite

from ...shared.logging import get_logger
from ...shared.models.assessment import EvidenceReference, ImpactAssessment
from ...shared.models.clients import ClientExposure
from ...shared.models.scoring import RiskScore
from ...shared.ports.assessment_store import AssessmentStorePort

logger = get_logger("persistence.sqlite.assessments")

_DDL = """
CREATE TABLE IF NOT EXISTS assessments (
    id                      TEXT PRIMARY KEY,
    event_id                TEXT NOT NULL,
    client_id               TEXT NOT NULL,
    project_id              TEXT,
    correlation_id          TEXT NOT NULL,
    assessment_text         TEXT NOT NULL,
    key_risks               TEXT NOT NULL DEFAULT '[]',
    recommended_actions     TEXT NOT NULL DEFAULT '[]',
    evidence_references     TEXT NOT NULL DEFAULT '[]',
    model_provider          TEXT NOT NULL,
    model_version           TEXT NOT NULL,
    raw_model_output        TEXT NOT NULL DEFAULT '{}',
    assessed_at             TEXT NOT NULL,
    processing_duration_ms  INTEGER
);

CREATE TABLE IF NOT EXISTS risk_scores (
    id                          TEXT PRIMARY KEY,
    assessment_id               TEXT NOT NULL REFERENCES assessments(id),
    event_id                    TEXT NOT NULL,
    client_id                   TEXT NOT NULL,
    project_id                  TEXT,
    overall_score               REAL NOT NULL,
    severity_component          REAL NOT NULL,
    exposure_component          REAL NOT NULL,
    confidence_component        REAL NOT NULL,
    risk_level                  TEXT NOT NULL,
    scoring_algorithm_version   TEXT NOT NULL,
    factors                     TEXT NOT NULL DEFAULT '{}',
    scored_at                   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_exposures (
    id                  TEXT PRIMARY KEY,
    client_id           TEXT NOT NULL,
    event_id            TEXT NOT NULL,
    project_id          TEXT,
    relevance_score     REAL NOT NULL,
    matched_keywords    TEXT NOT NULL DEFAULT '[]',
    matched_geography   TEXT NOT NULL DEFAULT '[]',
    assessed_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assessments_event   ON assessments(event_id);
CREATE INDEX IF NOT EXISTS idx_assessments_client  ON assessments(client_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_assess  ON risk_scores(assessment_id);
CREATE INDEX IF NOT EXISTS idx_exposures_event     ON client_exposures(event_id);
"""


class SQLiteAssessmentStore(AssessmentStorePort):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialise(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._db.execute(stmt)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ── AssessmentStorePort ───────────────────────────────────────────────────

    async def save_assessment(self, assessment: ImpactAssessment) -> None:
        await self._db.execute(
            """
            INSERT INTO assessments (
                id, event_id, client_id, project_id, correlation_id,
                assessment_text, key_risks, recommended_actions,
                evidence_references, model_provider, model_version,
                raw_model_output, assessed_at, processing_duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                assessment.id,
                assessment.event_id,
                assessment.client_id,
                assessment.project_id,
                assessment.correlation_id,
                assessment.assessment_text,
                json.dumps(assessment.key_risks),
                json.dumps(assessment.recommended_actions),
                json.dumps([e.model_dump() for e in assessment.evidence_references]),
                assessment.model_provider,
                assessment.model_version,
                json.dumps(assessment.raw_model_output),
                assessment.assessed_at.isoformat(),
                assessment.processing_duration_ms,
            ),
        )
        await self._db.commit()

    async def get_assessment(self, assessment_id: str) -> Optional[ImpactAssessment]:
        async with self._db.execute(
            "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_assessment(row) if row else None

    async def list_assessments(
        self,
        event_id: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ImpactAssessment]:
        conditions, params = [], []
        if event_id:
            conditions.append("event_id = ?")
            params.append(event_id)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        async with self._db.execute(
            f"SELECT * FROM assessments {where} ORDER BY assessed_at DESC LIMIT ?",
            params,
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_assessment(r) for r in rows]

    async def save_risk_score(self, score: RiskScore) -> None:
        await self._db.execute(
            """
            INSERT INTO risk_scores (
                id, assessment_id, event_id, client_id, project_id,
                overall_score, severity_component, exposure_component,
                confidence_component, risk_level, scoring_algorithm_version,
                factors, scored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                score.id,
                score.assessment_id,
                score.event_id,
                score.client_id,
                score.project_id,
                score.overall_score,
                score.severity_component,
                score.exposure_component,
                score.confidence_component,
                str(score.risk_level),
                score.scoring_algorithm_version,
                json.dumps(score.factors),
                score.scored_at.isoformat(),
            ),
        )
        await self._db.commit()

    async def get_risk_score(self, assessment_id: str) -> Optional[RiskScore]:
        async with self._db.execute(
            "SELECT * FROM risk_scores WHERE assessment_id = ?", (assessment_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_score(row) if row else None

    async def save_client_exposure(self, exposure: ClientExposure) -> None:
        await self._db.execute(
            """
            INSERT INTO client_exposures (
                id, client_id, event_id, project_id,
                relevance_score, matched_keywords, matched_geography, assessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                exposure.id,
                exposure.client_id,
                exposure.event_id,
                exposure.project_id,
                exposure.relevance_score,
                json.dumps(exposure.matched_keywords),
                json.dumps(exposure.matched_geography),
                exposure.assessed_at.isoformat(),
            ),
        )
        await self._db.commit()

    async def list_exposures(self, event_id: str) -> list[ClientExposure]:
        async with self._db.execute(
            """
            SELECT * FROM client_exposures
            WHERE event_id = ?
            ORDER BY relevance_score DESC
            """,
            (event_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_exposure(r) for r in rows]


# ── Row mappers ───────────────────────────────────────────────────────────────


def _row_to_assessment(row) -> ImpactAssessment:
    evidence_data = json.loads(row["evidence_references"])
    return ImpactAssessment(
        id=row["id"],
        event_id=row["event_id"],
        client_id=row["client_id"],
        project_id=row["project_id"],
        correlation_id=row["correlation_id"],
        assessment_text=row["assessment_text"],
        key_risks=json.loads(row["key_risks"]),
        recommended_actions=json.loads(row["recommended_actions"]),
        evidence_references=[EvidenceReference(**e) for e in evidence_data],
        model_provider=row["model_provider"],
        model_version=row["model_version"],
        raw_model_output=json.loads(row["raw_model_output"]),
        assessed_at=datetime.fromisoformat(row["assessed_at"]),
        processing_duration_ms=row["processing_duration_ms"],
    )


def _row_to_score(row) -> RiskScore:
    return RiskScore(
        id=row["id"],
        assessment_id=row["assessment_id"],
        event_id=row["event_id"],
        client_id=row["client_id"],
        project_id=row["project_id"],
        overall_score=row["overall_score"],
        severity_component=row["severity_component"],
        exposure_component=row["exposure_component"],
        confidence_component=row["confidence_component"],
        risk_level=row["risk_level"],
        scoring_algorithm_version=row["scoring_algorithm_version"],
        factors=json.loads(row["factors"]),
        scored_at=datetime.fromisoformat(row["scored_at"]),
    )


def _row_to_exposure(row) -> ClientExposure:
    return ClientExposure(
        id=row["id"],
        client_id=row["client_id"],
        event_id=row["event_id"],
        project_id=row["project_id"],
        relevance_score=row["relevance_score"],
        matched_keywords=json.loads(row["matched_keywords"]),
        matched_geography=json.loads(row["matched_geography"]),
        assessed_at=datetime.fromisoformat(row["assessed_at"]),
    )
