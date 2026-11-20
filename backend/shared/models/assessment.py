"""
Impact assessment data contracts.

``ImpactAssessment`` retains the full model provenance chain: which provider
was used, its version, and the validated raw output.  This enables offline
re-scoring and audit without re-querying the model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .events import utcnow


class EvidenceReference(BaseModel):
    """
    A single piece of retrieved evidence supporting an assessment.

    Every assessment must cite its evidence; assertions without an
    ``EvidenceReference`` are not persisted.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_document_id: str = Field(description="ID of the indexed source document")
    source_type: str = Field(
        description="One of: client_profile, project_document, knowledge_base, regional_profile"
    )
    content_excerpt: str = Field(description="The retrieved passage used as evidence")
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Retrieval score from the knowledge repository (never from an LLM)",
    )
    retrieval_strategy: str = Field(
        description="Strategy used to retrieve this document, e.g. lexical_bm25, dense_bge_m3"
    )


class ImpactAssessment(BaseModel):
    """
    A model-generated assessment validated against a schema and enriched with
    deterministic metadata before persistence.

    The LLM output is captured in ``raw_model_output`` for audit.  Business
    logic (risk scoring, routing) uses only the structured fields, never the
    raw text directly.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    client_id: str
    project_id: str | None = None
    correlation_id: str = Field(description="Propagated from the originating event")

    # ── Model-generated content (validated against AssessmentOutput schema) ──
    assessment_text: str
    key_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)

    # ── Evidence chain ───────────────────────────────────────────────────────
    evidence_references: list[EvidenceReference] = Field(default_factory=list)

    # ── Model provenance ─────────────────────────────────────────────────────
    model_provider: str = Field(description="Provider name, e.g. deterministic, gemini")
    model_version: str
    raw_model_output: dict = Field(
        description="Original validated model output retained verbatim for audit"
    )

    # ── Processing metadata ──────────────────────────────────────────────────
    assessed_at: datetime = Field(default_factory=utcnow)
    processing_duration_ms: int | None = None
