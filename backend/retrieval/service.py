"""
Retrieval service.

Thin orchestration layer between the assessment service and the
knowledge repository port.  Enriches the query with client context
and filters out low-relevance results.

Returns a ``RetrievalResult`` containing both the validated reference list
and the set of document IDs that were actually retrieved.  The assessment
service uses ``retrieved_ids`` to guard against LLM-fabricated citations:
any reference whose ``source_document_id`` is not in ``retrieved_ids`` is
dropped before the ``ImpactAssessment`` is built.
"""

from __future__ import annotations

from typing import NamedTuple

from ..shared.config import get_settings
from ..shared.logging import get_logger
from ..shared.models.assessment import EvidenceReference
from ..shared.models.clients import Client, Project
from ..shared.ports.knowledge_repository import KnowledgeRepositoryPort

logger = get_logger("retrieval")


class RetrievalResult(NamedTuple):
    """
    Return type of ``RetrievalService.retrieve()``.

    ``references``  — validated, relevance-filtered evidence references.
    ``retrieved_ids`` — frozenset of ``source_document_id`` values in
                        ``references``.  Passed to the assessment service
                        so it can reject any reference a live LLM fabricates
                        that was never actually retrieved.
    """

    references: list[EvidenceReference]
    retrieved_ids: frozenset[str]


class RetrievalService:
    def __init__(self, repository: KnowledgeRepositoryPort) -> None:
        self._repo = repository
        self._settings = get_settings()

    async def retrieve(
        self,
        query: str,
        client: Client,
        project: Project | None = None,
        correlation_id: str = "",
    ) -> RetrievalResult:
        """
        Retrieve relevant evidence for a client/event query.

        The query is enriched with client industry and geography so the
        repository can weight domain-relevant documents higher.

        Only evidence with relevance_score >= 0.1 is returned.
        Evidence IDs are always traceable back to indexed documents.

        Returns a ``RetrievalResult`` with both the filtered references and the
        set of retrieved document IDs for downstream citation validation.
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

        # Build the retrieved_ids set from the validated references only.
        # This set is passed to the assessment service to validate that no
        # references were fabricated by a live LLM provider.
        retrieved_ids: frozenset[str] = frozenset(
            ref.source_document_id for ref in validated
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

        return RetrievalResult(references=validated, retrieved_ids=retrieved_ids)
