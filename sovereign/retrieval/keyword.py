"""BM25 keyword index — in-process, no external service.

Provides keyword-based retrieval to complement vector search. The two
are combined via Reciprocal Rank Fusion (RRF) in ``HybridRetriever``.

BM25 (Best Matching 25) is the standard keyword ranking algorithm:
- TF-IDF with length normalization and saturation
- Better than raw TF-IDF for short-to-medium queries
- Deterministic, no training needed

The index is per-project: each project gets its own keyword index
instance, ensuring project isolation.

Limitation: this is an in-memory index rebuilt on startup from the DB.
For large corpora (>100k chunks), consider migrating to a proper
search engine (Elasticsearch, Meilisearch). The interface stays the same.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass

from sovereign.core.logging import get_logger
from sovereign.parsing.chunking import Chunk

log = get_logger(__name__)


@dataclass(slots=True)
class KeywordSearchResult:
    """A single keyword search result."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    page: int | None
    section_path: list[str]
    chunk_index: int
    block_kinds: list[str]


class BM25Index:
    """In-memory BM25 keyword index for a single project.

    Usage::

        index = BM25Index()
        index.add_chunks(chunks)
        results = index.search("pump maintenance", top_k=10)
        index.remove_document("doc_123")  # when a doc is deleted
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """BM25 parameters.

        k1: term frequency saturation (1.2-2.0 is standard)
        b:  length normalization (0.75 is standard; 0=no normalization)
        """
        self.k1 = k1
        self.b = b

        # Chunk storage
        self._chunks: dict[str, Chunk] = {}  # chunk_id → Chunk
        self._doc_chunks: dict[str, set[str]] = defaultdict(set)  # doc_id → {chunk_ids}
        self._tokenized: dict[str, list[str]] = {}  # chunk_id → tokens

        # Index statistics
        self._doc_freq: dict[str, int] = defaultdict(int)  # term → # chunks containing it
        self._doc_len: dict[str, int] = {}  # chunk_id → token count
        self._avg_doc_len: float = 0.0
        self._total_docs: int = 0

        # Term frequency per chunk
        self._term_freq: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add chunks to the index."""
        for chunk in chunks:
            self._add_chunk(chunk)
        self._update_avg_doc_len()

    def _add_chunk(self, chunk: Chunk) -> None:
        """Add a single chunk to the index."""
        if chunk.chunk_id in self._chunks:
            # Already indexed — skip (caller should remove first to update)
            return

        tokens = _tokenize(chunk.text)
        self._chunks[chunk.chunk_id] = chunk
        self._tokenized[chunk.chunk_id] = tokens
        self._doc_len[chunk.chunk_id] = len(tokens)
        self._total_docs += 1

        # Track document membership
        if chunk.document_id:
            self._doc_chunks[chunk.document_id].add(chunk.chunk_id)

        # Term frequencies + document frequencies
        tf: dict[str, int] = defaultdict(int)
        for token in tokens:
            tf[token] += 1
        self._term_freq[chunk.chunk_id] = tf

        for term in set(tokens):
            self._doc_freq[term] += 1

    def remove_chunk(self, chunk_id: str) -> None:
        """Remove a single chunk from the index."""
        if chunk_id not in self._chunks:
            return

        chunk = self._chunks[chunk_id]
        tokens = self._tokenized[chunk_id]

        # Remove from doc_chunks
        if chunk.document_id:
            self._doc_chunks[chunk.document_id].discard(chunk_id)
            if not self._doc_chunks[chunk.document_id]:
                del self._doc_chunks[chunk.document_id]

        # Update doc_freq
        for term in set(tokens):
            self._doc_freq[term] -= 1
            if self._doc_freq[term] <= 0:
                del self._doc_freq[term]

        # Remove from all structures
        del self._chunks[chunk_id]
        del self._tokenized[chunk_id]
        del self._doc_len[chunk_id]
        del self._term_freq[chunk_id]
        self._total_docs -= 1

        self._update_avg_doc_len()

    def remove_document(self, document_id: str) -> int:
        """Remove all chunks belonging to a document. Returns count removed."""
        chunk_ids = list(self._doc_chunks.get(document_id, set()))
        for cid in chunk_ids:
            self.remove_chunk(cid)
        log.info("bm25.doc_removed", document_id=document_id, removed=len(chunk_ids))
        return len(chunk_ids)

    def search(self, query: str, top_k: int = 10) -> list[KeywordSearchResult]:
        """Search the index for the query. Returns ranked results."""
        if self._total_docs == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = {}
        for chunk_id in self._chunks:
            score = self._bm25_score(chunk_id, query_tokens)
            if score > 0:
                scores[chunk_id] = score

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            KeywordSearchResult(
                chunk_id=cid,
                document_id=self._chunks[cid].document_id,
                text=self._chunks[cid].text,
                score=score,
                page=self._chunks[cid].page,
                section_path=self._chunks[cid].section_path,
                chunk_index=self._chunks[cid].chunk_index,
                block_kinds=self._chunks[cid].block_kinds,
            )
            for cid, score in ranked
        ]

    def _bm25_score(self, chunk_id: str, query_tokens: list[str]) -> float:
        """Compute BM25 score for a chunk given query tokens."""
        score = 0.0
        doc_len = self._doc_len.get(chunk_id, 0)
        tf_map = self._term_freq.get(chunk_id, {})

        for term in query_tokens:
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue

            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue

            # IDF with smoothing
            idf = math.log(1 + (self._total_docs - df + 0.5) / (df + 0.5))

            # TF saturation
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1))
            )

            score += idf * tf_norm

        return score

    def _update_avg_doc_len(self) -> None:
        if self._total_docs > 0 and self._doc_len:
            self._avg_doc_len = sum(self._doc_len.values()) / self._total_docs
        else:
            self._avg_doc_len = 0.0

    @property
    def size(self) -> int:
        """Number of chunks in the index."""
        return self._total_docs


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\b\w+\b", re.UNICODE)

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "must", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "about", "through", "during", "before", "after", "above",
    "below", "between", "this", "that", "these", "those", "i", "you",
    "he", "she", "it", "we", "they", "what", "which", "who", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "not", "only", "own", "same",
    "so", "than", "too", "very", "can", "just",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, split on word boundaries, remove stopwords."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
