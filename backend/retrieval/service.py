"""
Retrieval service.

Thin orchestration layer between the assessment service and the
knowledge repository port.  Enriches the query with client context
and filters out low-relevance results.
"""

from __future__ import annotations

from typing import Optional

from ..shared.config import get_settings
from ..shared.logging import get_logger
from ..shared.models.assessment import EvidenceReference
from ..shared.models.clients import Client, Project
from ..shared.ports.knowledge_repository import KnowledgeRepositoryPort

logger = get_logger("retrieval")


class RetrievalService:
    def __init__(self, repository: KnowledgeRepositoryPort) -> None:
        self._repo = repository
        self._settings = get_settings()

    async def retrieve(
        self,
        query: str,
        client: Client,
        project: Optional[Project] = None,
        correlation_id: str = "",
    ) -> list[EvidenceReference]:
        """
        Retrieve relevant evidence for a client/event query.

        The query is enriched with client industry and geography so the
        repository can weight domain-relevant documents higher.

        Only evidence with relevance_score >= 0.1 is returned.
        Evidence IDs are always traceable back to indexed documents.
        """
        enriched = (
            f"{query} {client.industry} {' '.join(client.geography)}"
        )
        if project:
            enriched += f" {project.name} {project.description}"

        all_refs = await self._repo.search(
            query=enriched,
            top_k=self._settings.retrieval_top_k,
        )

        filtered = [r for r in all_refs if r.relevance_score >= 0.1]

        # Citation validation: drop references to documents not in the index
        validated: list[EvidenceReference] = []
        for ref in filtered:
            if await self._repo.document_exists(ref.source_document_id):
                validated.append(ref)
            else:
                logger.warning(
                    "Dropping evidence reference: document not found in index",
                    extra={
                        "source_document_id": ref.source_document_id,
                        "correlation_id": correlation_id,
                    },
                )

        logger.debug(
            "Evidence retrieved",
            extra={
                "client_id": client.id,
                "retrieved": len(all_refs),
                "after_filter": len(filtered),
                "after_validation": len(validated),
                "strategy": "lexical_bm25",
            },
        )

        return validated
