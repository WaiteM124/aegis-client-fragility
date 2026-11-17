"""
Contract tests for KnowledgeRepositoryPort.

Every concrete implementation must satisfy this contract.
Add new adapters to the ``repo`` fixture — no other changes needed.

Contract requirements:
  1. index_document + search returns relevant results.
  2. document_exists returns True for indexed docs, False for unknown IDs.
  3. Documents indexed without an explicit ID get a stable, deterministic ID
     across separate index calls for the same content.
  4. Searching an empty repository returns [].
"""

from __future__ import annotations

import pytest

from backend.persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from backend.shared.ports.knowledge_repository import KnowledgeRepositoryPort


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(params=["lexical"])
async def repo(request) -> KnowledgeRepositoryPort:
    if request.param == "lexical":
        return LexicalKnowledgeRepository()
    raise ValueError(f"Unknown repository type: {request.param}")


# ── Contract test class ───────────────────────────────────────────────────────


class TestKnowledgeRepositoryContract:

    async def test_index_and_retrieve(self, repo):
        """Index one document and confirm a term search returns it with score > 0."""
        await repo.index_document(
            document_id="contract-doc-001",
            content=(
                "Geopolitical tensions in Eastern Europe affect investment banking "
                "operations and cross-border capital flows between European nations."
            ),
            source_type="intelligence_report",
            metadata={"id": "contract-doc-001"},
        )

        results = await repo.search(query="geopolitical investment banking europe", top_k=5)

        assert len(results) == 1
        assert results[0].source_document_id == "contract-doc-001"
        assert results[0].relevance_score > 0

    async def test_document_exists_true(self, repo):
        """document_exists returns True for a document that has been indexed."""
        await repo.index_document(
            document_id="exists-doc-001",
            content="Cyber attack on financial infrastructure in Europe.",
            source_type="intelligence_report",
            metadata={"id": "exists-doc-001"},
        )

        result = await repo.document_exists("exists-doc-001")

        assert result is True

    async def test_document_exists_false(self, repo):
        """document_exists returns False for an ID that was never indexed."""
        result = await repo.document_exists("nonexistent-id-xyz-99999")

        assert result is False

    async def test_stable_ids_across_reindex(self, repo):
        """
        Indexing a document without an explicit 'id' should produce a
        deterministic ID. Re-indexing the same content (via load_from_directory)
        must return the same document ID.

        We test this by using the LexicalKnowledgeRepository.load_from_directory
        with a temporary JSON file, then confirming the ID is stable.
        """
        import json
        import os
        import tempfile

        # Build a temp directory with one JSON file (no 'id' field)
        doc_content = {
            "title": "Stable ID Test Document",
            "content": "This document has no explicit id field and should get a deterministic hash.",
            "region": "Global",
            "industry": "technology",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test_stable.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump([doc_content], fh)

            # First load
            repo1 = LexicalKnowledgeRepository()
            await repo1.load_from_directory(tmpdir)
            results1 = await repo1.search(query="stable id deterministic hash technology", top_k=5)
            assert len(results1) == 1
            first_id = results1[0].source_document_id

            # Second load — same content, should produce same ID
            repo2 = LexicalKnowledgeRepository()
            await repo2.load_from_directory(tmpdir)
            results2 = await repo2.search(query="stable id deterministic hash technology", top_k=5)
            assert len(results2) == 1
            second_id = results2[0].source_document_id

        assert first_id == second_id, (
            f"Expected stable IDs across reindex, got {first_id!r} != {second_id!r}"
        )

    async def test_empty_search_returns_empty(self, repo):
        """Searching an empty repository returns an empty list, not an error."""
        results = await repo.search(query="anything at all", top_k=5)

        assert results == []
