"""
Events API.

POST /events  — Submit a global event for asynchronous processing.
               Returns 202 Accepted immediately; processing is independent.
GET  /events  — List recent events with status.
GET  /events/{id} — Event detail with classification and assessments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...ingestion.service import DuplicateEventError, IngestionService
from ...shared.logging import get_logger

router = APIRouter()
logger = get_logger("api.events")


# ── Request / response schemas ────────────────────────────────────────────────


class IngestEventRequest(BaseModel):
    source: str = Field(..., description="Source identifier, e.g. reuters, ap, manual")
    title: str = Field(..., min_length=5, max_length=500)
    raw_content: str = Field(..., min_length=10)
    event_date: datetime
    source_url: Optional[str] = None
    location: Optional[str] = None
    affected_regions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(
        None,
        description=(
            "Caller-supplied deduplication key. "
            "Re-submitting a known key returns 409 Conflict."
        ),
    )


class IngestEventResponse(BaseModel):
    event_id: str
    correlation_id: str
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=IngestEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a global event",
    description=(
        "Accepts a global event for asynchronous processing. "
        "Returns immediately with a correlation ID. "
        "The event is published to the message bus; "
        "the worker processes it independently."
    ),
)
async def ingest_event(request: Request, body: IngestEventRequest):
    container = request.app.state.container
    service: IngestionService = container.ingestion_service

    try:
        event = await service.ingest_event(
            source=body.source,
            title=body.title,
            raw_content=body.raw_content,
            event_date=body.event_date,
            source_url=body.source_url,
            location=body.location,
            affected_regions=body.affected_regions,
            tags=body.tags,
            idempotency_key=body.idempotency_key,
        )
    except DuplicateEventError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Event already processed: idempotency_key={exc.idempotency_key!r}",
        ) from exc

    return IngestEventResponse(
        event_id=event.id,
        correlation_id=event.correlation_id,
        status=str(event.status),
        message="Event accepted for processing",
    )


@router.get("", summary="List recent events")
async def list_events(request: Request, limit: int = 20, offset: int = 0):
    container = request.app.state.container
    events = await container.event_store.list_events(limit=limit, offset=offset)
    return {
        "events": [e.model_dump(mode="json") for e in events],
        "count": len(events),
    }


@router.get("/{event_id}", summary="Event detail with classification and assessments")
async def get_event(request: Request, event_id: str):
    container = request.app.state.container
    event = await container.event_store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    classification = await container.event_store.get_classification(event_id)
    assessments = await container.assessment_store.list_assessments(event_id=event_id)

    # Attach risk scores inline
    assessments_out = []
    for a in assessments:
        score = await container.assessment_store.get_risk_score(a.id)
        assessments_out.append({
            **a.model_dump(mode="json"),
            "risk_score": score.model_dump(mode="json") if score else None,
        })

    return {
        "event": event.model_dump(mode="json"),
        "classification": classification.model_dump(mode="json") if classification else None,
        "assessments": assessments_out,
    }
