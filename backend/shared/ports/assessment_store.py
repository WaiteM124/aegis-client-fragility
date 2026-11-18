"""Port: assessment, risk score, and client exposure persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models.assessment import ImpactAssessment
from ..models.clients import ClientExposure
from ..models.scoring import RiskScore


class AssessmentStorePort(ABC):

    @abstractmethod
    async def save_assessment(self, assessment: ImpactAssessment) -> None:
        ...

    @abstractmethod
    async def get_assessment(self, assessment_id: str) -> Optional[ImpactAssessment]:
        ...

    @abstractmethod
    async def list_assessments(
        self,
        event_id: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ImpactAssessment]:
        ...

    @abstractmethod
    async def save_risk_score(self, score: RiskScore) -> None:
        ...

    @abstractmethod
    async def get_risk_score(self, assessment_id: str) -> Optional[RiskScore]:
        ...

    @abstractmethod
    async def save_client_exposure(self, exposure: ClientExposure) -> None:
        ...

    @abstractmethod
    async def list_exposures(self, event_id: str) -> list[ClientExposure]:
        ...

    # ── Aggregation ───────────────────────────────────────────────────────────

    async def get_assessments_summary(self) -> dict:
        """Return total count, counts by risk level, and distinct client count.

        Return shape: {"total": int, "by_risk_level": {str: int}, "clients_affected": int}
        """
        return {"total": 0, "by_risk_level": {}, "clients_affected": 0}

    async def list_exposures_by_assessment(self, assessment_id: str) -> list[ClientExposure]:
        """Return client exposures for a given assessment."""
        return []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialise(self) -> None:
        """Create tables / indexes.  Called once at startup."""

    async def close(self) -> None:
        """Release connections."""
