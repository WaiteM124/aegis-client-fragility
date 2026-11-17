"""
BM25 lexical knowledge repository.

Implements KnowledgeRepositoryPort using an in-memory inverted index.
No external dependencies beyond Python stdlib.

BGE-M3 is a plug-in adapter when configured — the port interface is
identical; only the retrieval_strategy field in EvidenceReference changes.

BM25 parameters:
  k1 = 1.5  (term frequency saturation)
  b  = 0.75 (document length normalisation)
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from ...shared.logging import get_logger
from ...shared.models.assessment import EvidenceReference
from ...shared.ports.knowledge_repository import KnowledgeRepositoryPort

logger = get_logger("knowledge_repository.lexical")

K1 = 1.5
B = 0.75
MIN_TOKEN_LENGTH = 2
STRATEGY = "lexical_bm25"


class LexicalKnowledgeRepository(KnowledgeRepositoryPort):
    def __init__(self) -> None:
        # doc_id → {content, source_type, metadata}
        self._documents: dict[str, dict] = {}
        # term → {doc_id: frequency}
        self._index: dict[str, dict[str, int]] = defaultdict(dict)
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0

    # ── KnowledgeRepositoryPort ───────────────────────────────────────────────

    async def index_document(
        self,
        document_id: str,
        content: str,
        source_type: str,
        metadata: dict,
    ) -> None:
        tokens = _tokenise(content)
        self._documents[document_id] = {
            "content": content,
            "source_type": source_type,
            "metadata": metadata,
        }
        self._doc_lengths[document_id] = len(tokens)

        freq: dict[str, int] = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        for term, f in freq.items():
            self._index[term][document_id] = f

        self._avg_doc_length = sum(self._doc_lengths.values()) / max(
            len(self._doc_lengths), 1
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: Optional[list[str]] = None,
    ) -> list[EvidenceReference]:
        if not self._documents:
            return []

        query_tokens = _tokenise(query)
        scores: dict[str, float] = defaultdict(float)
        N = len(self._documents)

        for term in query_tokens:
            posting = self._index.get(term)
            if not posting:
                continue
            df = len(posting)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            for doc_id, tf in posting.items():
                dl = self._doc_lengths.get(doc_id, 1)
                tf_norm = (tf * (K1 + 1)) / (
                    tf + K1 * (1 - B + B * dl / max(self._avg_doc_length, 1))
                )
                scores[doc_id] += idf * tf_norm

        if source_types:
            scores = {
                d: s
                for d, s in scores.items()
                if self._documents[d]["source_type"] in source_types
            }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        if not ranked:
            return []

        max_score = ranked[0][1]

        results: list[EvidenceReference] = []
        for doc_id, raw_score in ranked:
            doc = self._documents[doc_id]
            norm = round(raw_score / max(max_score, 1e-9), 4)
            excerpt = _extract_excerpt(doc["content"], query_tokens)
            results.append(
                EvidenceReference(
                    source_document_id=doc_id,
                    source_type=doc["source_type"],
                    content_excerpt=excerpt,
                    relevance_score=norm,
                    retrieval_strategy=STRATEGY,
                )
            )

        return results

    async def document_count(self) -> int:
        return len(self._documents)

    async def document_exists(self, document_id: str) -> bool:
        return document_id in self._documents

    # ── Bulk loader ───────────────────────────────────────────────────────────

    async def load_from_directory(self, data_dir: str) -> int:
        """
        Index all JSON files found in ``data_dir``.

        Each JSON file may contain a list of objects or a single object.
        The file stem becomes the ``source_type``.
        """
        path = Path(data_dir)
        count = 0
        for json_file in sorted(path.glob("*.json")):
            try:
                with open(json_file, encoding="utf-8") as fh:
                    data = json.load(fh)

                items = data if isinstance(data, list) else [data]
                source_type = json_file.stem

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    doc_id = item.get("id") or hashlib.sha256(
                        f"{json_file.stem}:{json.dumps(item, sort_keys=True)}".encode()
                    ).hexdigest()[:16]
                    content = _dict_to_text(item)
                    await self.index_document(
                        document_id=doc_id,
                        content=content,
                        source_type=source_type,
                        metadata=item,
                    )
                    count += 1

            except Exception as exc:
                logger.warning(
                    "Failed to load knowledge file",
                    extra={"file": str(json_file), "error": str(exc)},
                )

        logger.info(
            "Knowledge base loaded",
            extra={"documents": count, "directory": str(data_dir)},
        )
        return count


# ── Helpers ───────────────────────────────────────────────────────────────────


def _tokenise(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"\b[a-z][a-z0-9]*\b", text)
    return [t for t in tokens if len(t) > MIN_TOKEN_LENGTH]


def _extract_excerpt(content: str, query_tokens: list[str], max_length: int = 250) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", content)
    best, best_score = sentences[0] if sentences else content, 0
    for s in sentences:
        score = sum(1 for t in query_tokens if t in s.lower())
        if score > best_score:
            best_score, best = score, s
    if len(best) > max_length:
        best = best[:max_length].rsplit(" ", 1)[0] + "…"
    return best


def _dict_to_text(d: dict) -> str:
    """Flatten a dict to a single searchable string."""
    parts: list[str] = []
    for val in d.values():
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val if isinstance(v, (str, int, float)))
        elif isinstance(val, (int, float)):
            parts.append(str(val))
    return " ".join(parts)
