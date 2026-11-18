"""
Dashboard API.

Returns aggregated statistics and recent activity for the intelligence
dashboard.  All aggregations use data already in the stores — no
additional model calls.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...shared.logging import get_logger

router = APIRouter()
logger = get_logger("api.dashboard")


@router.get("/summary", summary="Aggregated dashboard statistics")
async def get_dashboard_summary(request: Request):
    container = request.app.state.container

    all_events = await container.event_store.list_events(limit=500)
    all_assessments = await container.assessment_store.list_assessments(limit=500)

    # Event status breakdown
    status_counts: dict[str, int] = {}
    for e in all_events:
        s = str(e.status)
        status_counts[s] = status_counts.get(s, 0) + 1

    # Category and severity from classifications
    category_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for e in all_events:
        cls = await container.event_store.get_classification(e.id)
        if cls:
            cat = str(cls.category)
            sev = str(cls.severity)
            category_counts[cat] = category_counts.get(cat, 0) + 1
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Risk level breakdown
    risk_level_counts: dict[str, int] = {}
    for a in all_assessments:
        score = await container.assessment_store.get_risk_score(a.id)
        if score:
            lvl = str(score.risk_level)
            risk_level_counts[lvl] = risk_level_counts.get(lvl, 0) + 1

    # Affected clients / projects
    affected_clients: set[str] = set()
    affected_projects: set[str] = set()
    for e in all_events:
        exposures = await container.assessment_store.list_exposures(e.id)
        for exp in exposures:
            affected_clients.add(exp.client_id)
            if exp.project_id:
                affected_projects.add(exp.project_id)

    # Recent items (most recent first, capped at 10)
    recent_events = [e.model_dump(mode="json") for e in all_events[:10]]
    recent_assessments = [a.model_dump(mode="json") for a in all_assessments[:10]]

    return {
        "total_events": len(all_events),
        "total_assessments": len(all_assessments),
        "affected_clients": len(affected_clients),
        "affected_projects": len(affected_projects),
        "event_status_breakdown": status_counts,
        "category_breakdown": category_counts,
        "severity_breakdown": severity_counts,
        "risk_level_breakdown": risk_level_counts,
        "recent_events": recent_events,
        "recent_assessments": recent_assessments,
    }


@router.get("/stats", summary="Aggregated stats: event and assessment counts")
async def get_stats(request: Request):
    """
    Returns a flat summary of event and assessment counts suitable for
    a dashboard KPI row.  All values come from the stores — no model calls.
    """
    container = request.app.state.container

    events_summary = await container.event_store.get_events_summary()
    assessments_summary = await container.assessment_store.get_assessments_summary()

    return {
        "total_events": events_summary.get("total", 0),
        "events_by_status": events_summary.get("by_status", {}),
        "events_by_severity": events_summary.get("by_severity", {}),
        "total_assessments": assessments_summary.get("total", 0),
        "assessments_by_risk_level": assessments_summary.get("by_risk_level", {}),
        "clients_affected": assessments_summary.get("clients_affected", 0),
    }


@router.get("/events/{event_id}/trace", summary="Full provenance trace for one event")
async def get_event_trace(event_id: str, request: Request):
    """
    Returns the event, its classification, and all assessments (with risk
    scores and client exposures) in a single response.  Read-only — does
    not trigger any model calls.

    Returns 404 if the event does not exist.
    """
    container = request.app.state.container

    event = await container.event_store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")

    classification = await container.event_store.get_classification(event_id)
    assessments = await container.assessment_store.list_assessments(event_id=event_id)

    assessment_traces = []
    for a in assessments:
        risk_score = await container.assessment_store.get_risk_score(a.id)
        exposures = await container.assessment_store.list_exposures_by_assessment(a.id)
        client_exposure = exposures[0] if exposures else None

        assessment_traces.append({
            "assessment": a.model_dump(mode="json"),
            "risk_score": risk_score.model_dump(mode="json") if risk_score else None,
            "client_exposure": client_exposure.model_dump(mode="json") if client_exposure else None,
        })

    return {
        "event": event.model_dump(mode="json"),
        "classification": classification.model_dump(mode="json") if classification else None,
        "assessments": assessment_traces,
    }


@router.get("/assessments", summary="Recent assessments with risk scores")
async def list_dashboard_assessments(
    request: Request,
    limit: int = 20,
    client_id: str | None = None,
):
    container = request.app.state.container
    assessments = await container.assessment_store.list_assessments(
        client_id=client_id, limit=limit
    )

    result = []
    for a in assessments:
        score = await container.assessment_store.get_risk_score(a.id)
        result.append({
            **a.model_dump(mode="json"),
            "risk_score": score.model_dump(mode="json") if score else None,
        })
    return {"assessments": result, "count": len(result)}
