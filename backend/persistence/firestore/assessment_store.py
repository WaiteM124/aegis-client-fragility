"""
Firestore adapter for AssessmentStorePort.

Accepts an injected Firestore client so the emulator can be used in tests
without touching any live GCP project.

Collection names:
  - aegis_assessments   (ImpactAssessment documents)
  - aegis_risk_scores   (RiskScore documents)
  - aegis_exposures     (ClientExposure documents)
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from ...shared.logging import get_logger
from ...shared.models.assessment import EvidenceReference, ImpactAssessment
from ...shared.models.clients import ClientExposure
from ...shared.models.scoring import RiskScore
from ...shared.ports.assessment_store import AssessmentStorePort

logger = get_logger("persistence.firestore.assessments")

_ASSESSMENTS = "aegis_assessments"
_RISK_SCORES = "aegis_risk_scores"
_EXPOSURES = "aegis_exposures"


class FirestoreAssessmentStore(AssessmentStorePort):
    """
    Firestore-backed assessment store.

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

    # ── AssessmentStorePort ───────────────────────────────────────────────────

    async def save_assessment(self, assessment: ImpactAssessment) -> None:
        data = _assessment_to_dict(assessment)
        doc_ref = self._db.collection(_ASSESSMENTS).document(assessment.id)
        await asyncio.to_thread(doc_ref.set, data)

    async def get_assessment(self, assessment_id: str) -> ImpactAssessment | None:
        doc_ref = self._db.collection(_ASSESSMENTS).document(assessment_id)
        snap = await asyncio.to_thread(doc_ref.get)
        if not snap.exists:
            return None
        return _dict_to_assessment(snap.to_dict())

    async def list_assessments(
        self,
        event_id: str | None = None,
        client_id: str | None = None,
        limit: int = 50,
    ) -> list[ImpactAssessment]:
        def _query():
            col = self._db.collection(_ASSESSMENTS)
            q = col.order_by("assessed_at", direction="DESCENDING")
            if event_id:
                q = col.where("event_id", "==", event_id).order_by(
                    "assessed_at", direction="DESCENDING"
                )
            elif client_id:
                q = col.where("client_id", "==", client_id).order_by(
                    "assessed_at", direction="DESCENDING"
                )
            return list(q.limit(limit).stream())

        snaps = await asyncio.to_thread(_query)
        assessments = [_dict_to_assessment(s.to_dict()) for s in snaps]
        # Apply second filter in-memory if both event_id and client_id specified
        if event_id and client_id:
            assessments = [a for a in assessments if a.client_id == client_id]
        return assessments

    async def save_risk_score(self, score: RiskScore) -> None:
        data = _risk_score_to_dict(score)
        doc_ref = self._db.collection(_RISK_SCORES).document(score.id)
        await asyncio.to_thread(doc_ref.set, data)

    async def get_risk_score(self, assessment_id: str) -> RiskScore | None:
        def _query():
            return list(
                self._db.collection(_RISK_SCORES)
                .where("assessment_id", "==", assessment_id)
                .limit(1)
                .stream()
            )

        snaps = await asyncio.to_thread(_query)
        if not snaps:
            return None
        return _dict_to_risk_score(snaps[0].to_dict())

    async def save_client_exposure(self, exposure: ClientExposure) -> None:
        data = _exposure_to_dict(exposure)
        doc_ref = self._db.collection(_EXPOSURES).document(exposure.id)
        await asyncio.to_thread(doc_ref.set, data)

    async def list_exposures(self, event_id: str) -> list[ClientExposure]:
        def _query():
            return list(
                self._db.collection(_EXPOSURES)
                .where("event_id", "==", event_id)
                .order_by("relevance_score", direction="DESCENDING")
                .stream()
            )

        snaps = await asyncio.to_thread(_query)
        return [_dict_to_exposure(s.to_dict()) for s in snaps]

    async def list_exposures_by_assessment(self, assessment_id: str) -> list[ClientExposure]:
        """Return client exposures that share the same (event_id, client_id) as the assessment."""
        assessment = await self.get_assessment(assessment_id)
        if not assessment:
            return []

        def _query():
            return list(
                self._db.collection(_EXPOSURES)
                .where("event_id", "==", assessment.event_id)
                .where("client_id", "==", assessment.client_id)
                .stream()
            )

        snaps = await asyncio.to_thread(_query)
        return [_dict_to_exposure(s.to_dict()) for s in snaps]

    async def get_assessments_summary(self) -> dict:
        """Return total count, counts by risk level, and distinct client count."""

        def _fetch():
            assessments = list(self._db.collection(_ASSESSMENTS).stream())
            risk_scores = list(self._db.collection(_RISK_SCORES).stream())
            return assessments, risk_scores

        a_snaps, rs_snaps = await asyncio.to_thread(_fetch)

        client_ids = {s.to_dict().get("client_id") for s in a_snaps if s.to_dict().get("client_id")}

        by_risk_level: dict[str, int] = {}
        for snap in rs_snaps:
            d = snap.to_dict()
            lvl = d.get("risk_level", "unknown")
            by_risk_level[lvl] = by_risk_level.get(lvl, 0) + 1

        return {
            "total": len(a_snaps),
            "by_risk_level": by_risk_level,
            "clients_affected": len(client_ids),
        }


# ── Serialisers ───────────────────────────────────────────────────────────────


def _assessment_to_dict(a: ImpactAssessment) -> dict:
    return {
        "id": a.id,
        "event_id": a.event_id,
        "client_id": a.client_id,
        "project_id": a.project_id,
        "correlation_id": a.correlation_id,
        "assessment_text": a.assessment_text,
        "key_risks": a.key_risks,
        "recommended_actions": a.recommended_actions,
        "evidence_references": [e.model_dump() for e in a.evidence_references],
        "model_provider": a.model_provider,
        "model_version": a.model_version,
        "raw_model_output": a.raw_model_output,
        "assessed_at": a.assessed_at.isoformat(),
        "processing_duration_ms": a.processing_duration_ms,
    }


def _dict_to_assessment(d: dict) -> ImpactAssessment:
    evidence_data = d.get("evidence_references", [])
    return ImpactAssessment(
        id=d["id"],
        event_id=d["event_id"],
        client_id=d["client_id"],
        project_id=d.get("project_id"),
        correlation_id=d.get("correlation_id", ""),
        assessment_text=d["assessment_text"],
        key_risks=d.get("key_risks", []),
        recommended_actions=d.get("recommended_actions", []),
        evidence_references=[EvidenceReference(**e) for e in evidence_data],
        model_provider=d["model_provider"],
        model_version=d["model_version"],
        raw_model_output=d.get("raw_model_output", {}),
        assessed_at=datetime.fromisoformat(d["assessed_at"]),
        processing_duration_ms=d.get("processing_duration_ms"),
    )


def _risk_score_to_dict(s: RiskScore) -> dict:
    return {
        "id": s.id,
        "assessment_id": s.assessment_id,
        "event_id": s.event_id,
        "client_id": s.client_id,
        "project_id": s.project_id,
        "overall_score": s.overall_score,
        "severity_component": s.severity_component,
        "exposure_component": s.exposure_component,
        "confidence_component": s.confidence_component,
        "risk_level": str(s.risk_level),
        "scoring_algorithm_version": s.scoring_algorithm_version,
        "factors": s.factors,
        "scored_at": s.scored_at.isoformat(),
    }


def _dict_to_risk_score(d: dict) -> RiskScore:
    return RiskScore(
        id=d["id"],
        assessment_id=d["assessment_id"],
        event_id=d["event_id"],
        client_id=d["client_id"],
        project_id=d.get("project_id"),
        overall_score=d["overall_score"],
        severity_component=d["severity_component"],
        exposure_component=d["exposure_component"],
        confidence_component=d["confidence_component"],
        risk_level=d["risk_level"],
        scoring_algorithm_version=d["scoring_algorithm_version"],
        factors=d.get("factors", {}),
        scored_at=datetime.fromisoformat(d["scored_at"]),
    )


def _exposure_to_dict(e: ClientExposure) -> dict:
    return {
        "id": e.id,
        "client_id": e.client_id,
        "event_id": e.event_id,
        "project_id": e.project_id,
        "relevance_score": e.relevance_score,
        "matched_keywords": e.matched_keywords,
        "matched_geography": e.matched_geography,
        "assessed_at": e.assessed_at.isoformat(),
    }


def _dict_to_exposure(d: dict) -> ClientExposure:
    return ClientExposure(
        id=d["id"],
        client_id=d["client_id"],
        event_id=d["event_id"],
        project_id=d.get("project_id"),
        relevance_score=d["relevance_score"],
        matched_keywords=d.get("matched_keywords", []),
        matched_geography=d.get("matched_geography", []),
        assessed_at=datetime.fromisoformat(d["assessed_at"]),
    )
