"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...shared.logging import get_logger

router = APIRouter()
logger = get_logger("api.health")


@router.get("", summary="Liveness / readiness check")
async def health_check(request: Request):
    container = request.app.state.container
    model_ok = await container.model_provider.health_check()
    doc_count = await container.knowledge_repo.document_count()

    return {
        "status": "healthy",
        "model_provider": {
            "name": container.model_provider.provider_name,
            "version": container.model_provider.model_version,
            "healthy": model_ok,
        },
        "knowledge_base": {
            "documents_indexed": doc_count,
        },
    }
