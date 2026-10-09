"""Qdrant vector store client — embedded mode for dev, server for prod."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from sovereign.core.config import Settings, get_settings
from sovereign.core.errors import StorageError
from sovereign.core.logging import get_logger
from sovereign.parsing.chunking import Chunk

log = get_logger(__name__)


@dataclass(slots=True)
class VectorSearchResult:
    chunk_id: str
    document_id: str
    project_id: str
    text: str
    score: float
    page: int | None
    section_path: list[str]
    chunk_index: int
    block_kinds: list[str]


class QdrantStore:
    """Qdrant vector store with project-scoped collections."""

    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if self._settings.qdrant_url:
                api_key = self._settings.qdrant_api_key.get_secret_value() or None
                self._client = QdrantClient(url=self._settings.qdrant_url, api_key=api_key)
                log.info("qdrant.server_mode", url=self._settings.qdrant_url)
            else:
                self._client = QdrantClient(":memory:")
                log.info("qdrant.embedded_mode")
        return self._client

    def _collection_name(self, project_id: str) -> str:
        return f"sovereign_{project_id}".lower().replace("-", "_")

    def ensure_collection(self, project_id: str, dim: int) -> None:
        col_name = self._collection_name(project_id)
        try:
            self.client.get_collection(col_name)
            return
        except (UnexpectedResponse, Exception):
            pass
        try:
            self.client.create_collection(
                collection_name=col_name,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
            log.info("qdrant.collection_created", collection=col_name, dim=dim)
        except Exception as e:
            log.debug("qdrant.collection_create_skipped", collection=col_name, error=str(e))

    def delete_collection(self, project_id: str) -> None:
        col_name = self._collection_name(project_id)
        try:
            self.client.delete_collection(col_name)
            log.info("qdrant.collection_deleted", collection=col_name)
        except Exception:
            pass

    def upsert_chunks(
        self, project_id: str, chunks_with_vectors: list[tuple[Chunk, list[float]]]
    ) -> int:
        if not chunks_with_vectors:
            return 0
        col_name = self._collection_name(project_id)
        points: list[qmodels.PointStruct] = []
        for chunk, vector in chunks_with_vectors:
            point_id = _safe_point_id(chunk.chunk_id)
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "document_id": chunk.document_id,
                        "project_id": chunk.project_id,
                        "chunk_index": chunk.chunk_index,
                        "page": chunk.page,
                        "section_path": chunk.section_path,
                        "text": chunk.text,
                        "block_kinds": chunk.block_kinds,
                    },
                )
            )
        try:
            self.client.upsert(collection_name=col_name, points=points, wait=True)
        except Exception as e:
            msg = f"qdrant upsert failed: {e}"
            raise StorageError(msg) from e
        log.info("qdrant.upserted", collection=col_name, count=len(points))
        return len(points)

    def search(
        self,
        project_id: str,
        query_vector: list[float],
        top_k: int = 10,
        document_filter: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        col_name = self._collection_name(project_id)
        must_filter: list[qmodels.FieldCondition] | None = None
        if document_filter:
            must_filter = [
                qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v))
                for k, v in document_filter.items()
            ]
        try:
            try:
                response = self.client.query_points(
                    collection_name=col_name,
                    query=query_vector,
                    limit=top_k,
                    query_filter=qmodels.Filter(must=must_filter) if must_filter else None,
                )
                results = response.points
            except AttributeError:
                results = self.client.search(  # type: ignore[attr-defined]
                    collection_name=col_name,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=qmodels.Filter(must=must_filter) if must_filter else None,
                )
        except Exception as e:
            log.error("qdrant.search_failed", collection=col_name, error=str(e))
            return []
        return [
            VectorSearchResult(
                chunk_id=str(r.id),
                document_id=r.payload.get("document_id", "") if r.payload else "",
                project_id=r.payload.get("project_id", "") if r.payload else "",
                text=r.payload.get("text", "") if r.payload else "",
                score=r.score,
                page=r.payload.get("page") if r.payload else None,
                section_path=r.payload.get("section_path", []) if r.payload else [],
                chunk_index=r.payload.get("chunk_index", 0) if r.payload else 0,
                block_kinds=r.payload.get("block_kinds", []) if r.payload else [],
            )
            for r in results
        ]

    def delete_by_document(self, project_id: str, document_id: str) -> int:
        col_name = self._collection_name(project_id)
        try:
            self.client.delete(
                collection_name=col_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id", match=qmodels.MatchValue(value=document_id)
                            )
                        ]
                    )
                ),
                wait=True,
            )
            log.info("qdrant.deleted_by_doc", collection=col_name, document_id=document_id)
            return 0
        except Exception as e:
            log.error("qdrant.delete_failed", collection=col_name, error=str(e))
            return 0

    def count_points(self, project_id: str) -> int:
        col_name = self._collection_name(project_id)
        try:
            result = self.client.count(collection_name=col_name, count_filter=None, exact=True)
            return result.count
        except Exception:
            return 0


_store: QdrantStore | None = None


def get_qdrant_store(settings: Settings | None = None) -> QdrantStore:
    global _store  # noqa: PLW0603
    if _store is None:
        _store = QdrantStore(settings)
    return _store


def reset_qdrant_store() -> None:
    global _store  # noqa: PLW0603
    if _store is not None:
        try:
            _store._client = None
        except Exception:
            pass
    _store = None


def _safe_point_id(chunk_id: str) -> str | int:
    import hashlib

    h = hashlib.md5(chunk_id.encode()).hexdigest()
    return int(h[:15], 16)
