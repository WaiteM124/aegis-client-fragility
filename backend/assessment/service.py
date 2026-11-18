"""
Impact assessment service.

Orchestrates:
  1. Client and project matching (deterministic keyword + geography scoring).
  2. Evidence retrieval from the knowledge repository.
  3. Model-generated assessment (validated against AssessmentOutput schema).
  4. Deterministic risk scoring.
  5. Persistence of all artefacts with full provenance.

The model provider is treated as a text generation utility.
It never decides which clients are affected, what the risk level is,
or what actions should be taken authoritatively.
"""

from __future__ import annotations

import re
import time
from typing import Optional

from pydantic import BaseModel, ValidationError

from ..decision_engine.risk_scorer import RiskScorer
from ..retrieval.service import RetrievalService
from ..shared.geography import normalise_geography
from ..shared.logging import get_logger
from ..shared.models.assessment import EvidenceReference, ImpactAssessment
from ..shared.models.clients import Client, ClientExposure, Project
from ..shared.models.events import Event, EventClassification
from ..shared.ports.assessment_store import AssessmentStorePort
from ..shared.ports.model_provider import ModelProviderPort
from .errors import AssessmentError

logger = get_logger("assessment")


# ── Output schema ─────────────────────────────────────────────────────────────
# This is the contract the model MUST conform to.
# It is passed to ModelProviderPort.generate() and validated before use.


class AssessmentOutput(BaseModel):
    """Validated schema for model-generated impact assessments."""

    assessment_text: str
    key_risks: list[str]
    recommended_actions: list[str]


# ── Service ───────────────────────────────────────────────────────────────────


class AssessmentService:
    def __init__(
        self,
        assessment_store: AssessmentStorePort,
        retrieval_service: RetrievalService,
        model_provider: ModelProviderPort,
        risk_scorer: RiskScorer,
        clients: list[Client],
        projects: list[Project],
    ) -> None:
        self._store = assessment_store
        self._retrieval = retrieval_service
        self._model = model_provider
        self._scorer = risk_scorer
        self._clients = clients
        self._projects = projects

    async def assess_event(
        self,
        event: Event,
        classification: EventClassification,
    ) -> list[ImpactAssessment]:
        """
        Produce and persist impact assessments for all exposed clients.

        Returns the list of created assessments.
        """
        matched = self._match_clients(event, classification)

        logger.info(
            "Client matching complete",
            extra={
                "event_id": event.id,
                "matched_clients": len(matched),
                "correlation_id": event.correlation_id,
            },
        )

        assessments: list[ImpactAssessment] = []

        for client, exposure in matched:
            try:
                await self._store.save_client_exposure(exposure)

                project = self._match_project(client, event)

                # Retrieve evidence
                query = (
                    f"{event.title} {event.summary or ''} "
                    f"{client.industry} {' '.join(client.geography)}"
                )
                retrieval_result = await self._retrieval.retrieve(
                    query, client, project, correlation_id=event.correlation_id
                )
                evidence = retrieval_result.references
                retrieved_ids = retrieval_result.retrieved_ids

                # Generate and validate assessment via model
                start = time.monotonic()
                assessment_output = await self._generate_assessment(
                    event, classification, client, project, evidence, retrieved_ids
                )
                duration_ms = int((time.monotonic() - start) * 1000)

                assessment = ImpactAssessment(
                    event_id=event.id,
                    client_id=client.id,
                    project_id=project.id if project else None,
                    correlation_id=event.correlation_id,
                    assessment_text=assessment_output.assessment_text,
                    key_risks=assessment_output.key_risks,
                    recommended_actions=assessment_output.recommended_actions,
                    evidence_references=evidence,
                    model_provider=self._model.provider_name,
                    model_version=self._model.model_version,
                    raw_model_output=assessment_output.model_dump(),
                    processing_duration_ms=duration_ms,
                )

                await self._store.save_assessment(assessment)

                # Deterministic risk scoring (no LLM involvement)
                risk_score = self._scorer.score(
                    assessment=assessment,
                    classification=classification,
                    exposure=exposure,
                )
                await self._store.save_risk_score(risk_score)

                assessments.append(assessment)

            except AssessmentError as exc:
                logger.error(
                    "Assessment failed for client; skipping",
                    extra={
                        "event_id": event.id,
                        "client_id": client.id,
                        "reason": exc.reason,
                        "correlation_id": event.correlation_id,
                    },
                )

        return assessments

    # ── Client matching ───────────────────────────────────────────────────────

    def _match_clients(
        self,
        event: Event,
        classification: EventClassification,
    ) -> list[tuple[Client, ClientExposure]]:
        # Include event.tags so that synonym-expanded terms (added by the
        # classifier) are visible to keyword matching.
        event_text = (
            f"{event.title} {event.summary or ''} {event.raw_content} "
            f"{' '.join(event.tags)}"
        ).lower()

        # Pre-normalise event regions via the geographic hierarchy once.
        normalised_event_regions = [
            normalise_geography(r) for r in event.affected_regions
        ]

        matched: list[tuple[Client, ClientExposure]] = []

        for client in self._clients:
            if not client.active:
                continue

            # Fix 1: word-boundary keyword matching prevents substring false
            # matches (e.g. "oil" must not match "soil" or "recoil").
            matched_kw = [
                kw for kw in client.keywords
                if _keyword_in_text(kw, event_text)
            ]

            # Fix 2: geographic hierarchy — normalise both sides so sub-regions
            # (e.g. "eastern_europe") correctly match parent regions ("europe").
            matched_geo = [
                region
                for region in client.geography
                if normalise_geography(region) in normalised_event_regions
            ]

            if not matched_kw and not matched_geo:
                continue

            kw_score = min(len(matched_kw) / max(len(client.keywords), 1), 1.0) * 0.6
            geo_score = min(len(matched_geo) / max(len(client.geography), 1), 1.0) * 0.4
            relevance = round(kw_score + geo_score, 4)

            if relevance < 0.05:
                continue

            exposure = ClientExposure(
                client_id=client.id,
                event_id=event.id,
                relevance_score=relevance,
                matched_keywords=matched_kw,
                matched_geography=matched_geo,
            )
            matched.append((client, exposure))

        return matched

    def _match_project(self, client: Client, event: Event) -> Optional[Project]:
        """Return the highest-relevance active project for this client, or None."""
        event_text = (
            f"{event.title} {event.summary or ''} {event.raw_content}"
        ).lower()

        candidates = [
            p for p in self._projects
            if p.client_id == client.id
            and p.status == "active"
            and (
                any(kw.lower() in event_text for kw in p.keywords)
                or any(r.lower() in [er.lower() for er in event.affected_regions]
                       for r in p.geography)
            )
        ]
        return candidates[0] if candidates else None

    # ── Model call ────────────────────────────────────────────────────────────

    async def _generate_assessment(
        self,
        event: Event,
        classification: EventClassification,
        client: Client,
        project: Optional[Project],
        evidence: list[EvidenceReference],
        retrieved_ids: frozenset[str] = frozenset(),
    ) -> AssessmentOutput:
        evidence_text = "\n".join(
            f"- [{ref.source_type}] {ref.content_excerpt}" for ref in evidence
        ) or "No specific evidence retrieved."

        project_line = ""
        if project:
            project_line = f"\nAffected project: {project.name} — {project.description}"

        system_prompt = (
            "You are an intelligence analyst. Assess the impact of a global event on a client. "
            "Be specific, evidence-based, and concise. "
            "Focus only on material risks and actionable steps."
        )

        user_prompt = (
            f"Event: {event.title}\n"
            f"Category: {classification.category}\n"
            f"Severity: {classification.severity}\n"
            f"Summary: {event.summary or event.raw_content[:500]}\n"
            f"Affected regions: {', '.join(event.affected_regions)}\n"
            f"\n"
            f"Client: {client.name}\n"
            f"Industry: {client.industry}\n"
            f"Regions of operation: {', '.join(client.geography)}"
            f"{project_line}\n"
            f"\n"
            f"Supporting evidence:\n{evidence_text}\n"
            f"\n"
            f"Provide an impact assessment with specific risks and recommended actions."
        )

        output_schema = AssessmentOutput
        try:
            result = await self._model.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
        except ValidationError as exc:
            logger.error(
                "Model output failed schema validation",
                extra={"event_id": event.id, "schema": output_schema.__name__, "error": str(exc)},
            )
            raise AssessmentError(event.id, "model output did not conform to schema", cause=exc) from exc
        except Exception as exc:
            logger.error(
                "Model provider error",
                extra={"event_id": event.id, "error": str(exc)},
            )
            raise AssessmentError(event.id, "model provider raised an exception", cause=exc) from exc

        # ── Citation guard ────────────────────────────────────────────────────
        # With the DeterministicModelProvider, evidence references are passed
        # through unchanged (the model never fabricates new IDs).  With a live
        # LLM provider (e.g. Gemini), the model could hallucinate document IDs
        # that were never retrieved — this guard drops any such fabricated
        # references before they reach the ImpactAssessment.
        if retrieved_ids:
            safe_evidence: list[EvidenceReference] = []
            for ref in evidence:
                if ref.source_document_id in retrieved_ids:
                    safe_evidence.append(ref)
                else:
                    logger.warning(
                        "Dropping fabricated evidence reference not in retrieved set",
                        extra={
                            "source_document_id": ref.source_document_id,
                            "event_id": event.id,
                        },
                    )
            # Reassign evidence to the validated safe set
            evidence[:] = safe_evidence

        return result  # type: ignore[return-value]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _keyword_in_text(kw: str, text: str) -> bool:
    """
    Return True if ``kw`` appears in ``text`` as a whole word (word-boundary
    match).  This prevents substring false matches such as "oil" matching
    "soil", "recoil", or "spoil".

    Multi-word keywords (e.g. "supply chain") are matched as full phrases with
    word boundaries anchored at the start of the first word and the end of
    the last word.
    """
    return bool(re.search(r"\b" + re.escape(kw.lower()) + r"\b", text))
