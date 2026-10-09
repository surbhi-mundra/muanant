"""Retrieval — hybrid retrieval + fusion.

Submodules:
- ``keyword``  — BM25 keyword index (in-process, no external service)
- ``vector``   — vector search via Qdrant
- ``fusion``   — Reciprocal Rank Fusion (RRF) for combining results
- ``service``  — HybridRetriever combining vector + keyword with RRF
"""

from __future__ import annotations

from sovereign.retrieval.service import HybridRetriever, RetrievalResult

__all__ = ["HybridRetriever", "RetrievalResult"]
