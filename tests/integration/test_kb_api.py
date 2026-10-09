"""Integration tests for the knowledge base API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.app import create_app
from sovereign.core.config import reset_settings_cache
from sovereign.embeddings.indexing import reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.storage.db.base import init_schema, reset_engine
from sovereign.storage.objects import reset_object_store
from sovereign.storage.qdrant import reset_qdrant_store


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory):
    monkeypatch.setenv("DATABASE_URL", "mock://localhost/sovereign_test")
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    monkeypatch.setenv("OBJECT_STORE_FS_ROOT", str(tmp_path / "objects"))
    reset_settings_cache()
    reset_model_gateway()
    reset_engine()
    reset_object_store()
    reset_qdrant_store()
    reset_indexing_service()
    init_schema()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_engine()
    reset_model_gateway()
    reset_object_store()
    reset_qdrant_store()
    reset_indexing_service()
    reset_settings_cache()


def _upload_doc(client: TestClient, filename: str, content: bytes) -> str:
    """Helper: upload a document and return its ID."""
    resp = client.post(
        "/documents",
        files={"file": (filename, content, "text/plain")},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["document_id"]


def test_search_empty_kb(client: TestClient) -> None:
    """Searching an empty KB should return zero results."""
    resp = client.post("/search", json={"query": "test", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0


def test_kb_stats_empty(client: TestClient) -> None:
    """KB stats on an empty KB should show zero."""
    resp = client.get("/kb/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["keyword_index_size"] == 0
    assert body["vector_count"] == 0


def test_upload_then_search(client: TestClient) -> None:
    """Upload a document, then search for its content."""
    doc_id = _upload_doc(
        client,
        "maintenance.txt",
        b"Pump P-101 Maintenance Report\n\n"
        b"The bearing on pump P-101 shows excessive wear and requires replacement.",
    )

    # Search for content
    resp = client.post("/search", json={"query": "pump bearing wear", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    # The first result should be from our document
    assert body["results"][0]["document_id"] == doc_id


def test_kb_stats_after_indexing(client: TestClient) -> None:
    """After uploading, KB stats should show non-zero counts."""
    _upload_doc(client, "test.txt", b"This is a test document with some content for indexing.")
    resp = client.get("/kb/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["keyword_index_size"] > 0
    assert body["vector_count"] > 0


def test_manual_reindex(client: TestClient) -> None:
    """POST /documents/{id}/index should re-index a document."""
    doc_id = _upload_doc(client, "test.txt", b"Document content for reindexing test.")

    resp = client.post(f"/documents/{doc_id}/index")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "indexed"
    assert body["chunk_count"] > 0


def test_remove_from_index(client: TestClient) -> None:
    """DELETE /documents/{id}/index should remove from KB."""
    doc_id = _upload_doc(client, "test.txt", b"Removable content for index test.")

    # Verify it's searchable
    resp = client.post("/search", json={"query": "removable content", "top_k": 5})
    assert resp.json()["total"] > 0

    # Remove from index
    resp = client.delete(f"/documents/{doc_id}/index")
    assert resp.status_code == 204

    # Should no longer be searchable
    resp = client.post("/search", json={"query": "removable content", "top_k": 5})
    assert resp.json()["total"] == 0


def test_search_with_document_filter(client: TestClient) -> None:
    """Search with a document_id filter should restrict results."""
    doc1 = _upload_doc(client, "doc1.txt", b"pump maintenance alpha")
    _upload_doc(client, "doc2.txt", b"pump maintenance beta")

    resp = client.post(
        "/search",
        json={"query": "pump maintenance", "top_k": 10, "document_id": doc1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(r["document_id"] == doc1 for r in body["results"])


def test_search_results_have_provenance(client: TestClient) -> None:
    """Search results should include page, section_path, chunk_index."""
    _upload_doc(
        client,
        "report.txt",
        b"# Chapter 1\n\nPump inspection reveals bearing wear on P-101.\n\n"
        b"## Section 2\n\nMaintenance required.",
    )
    resp = client.post("/search", json={"query": "pump bearing", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    r = body["results"][0]
    assert "chunk_id" in r
    assert "document_id" in r
    assert "text" in r
    assert "score" in r
    assert "section_path" in r
    assert "chunk_index" in r
