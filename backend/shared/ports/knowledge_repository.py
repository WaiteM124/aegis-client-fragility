"""
Port: knowledge repository / retrieval.

Concrete adapters:
  - LexicalKnowledgeRepository  — BM25, zero dependencies, default
  - BGEm3KnowledgeRepository    — BGE-M3 dense embeddings (opt-in, checkpoint 3)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models.assessment import EvidenceReference


class KnowledgeRepositoryPort(ABC):

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: Optional[list[str]] = None,
    ) -> list[EvidenceReference]:
        """
        Retrieve the top-k most relevant evidence references for a query.

        Returned scores are normalised to [0, 1].  The caller is responsible
        for filtering on a minimum threshold.
        """
        ...

    @abstractmethod
    async def index_document(
        self,
        document_id: str,
        content: str,
        source_type: str,
        metadata: dict,
    ) -> None:
        """Add or update a document in the index."""
        ...

    @abstractmethod
    async def document_count(self) -> int:
        """Return the number of indexed documents."""
        ...

    @abstractmethod
    async def document_exists(self, document_id: str) -> bool:
        """Return True if document_id is present in the index."""
        ...
