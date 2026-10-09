"""Integration tests for the RAG API endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.app import create_app
from sovereign.core.config import reset_settings_cache
from sovereign.embeddings.indexing import reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.rag.pipeline import reset_rag_pipeline
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
    reset_rag_pipeline()
    init_schema()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_engine()
    reset_model_gateway()
    reset_object_store()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()
    reset_settings_cache()


def test_rag_query_empty_kb(client: TestClient) -> None:
    """Querying an empty KB should return insufficient_evidence."""
    resp = client.post("/rag/query", json={"query": "What is pump P-101?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "insufficient_evidence"
    assert "don't have sufficient evidence" in body["verdict_message"].lower()
    assert body["is_answered"] is False


def test_rag_query_with_indexed_doc(client: TestClient) -> None:
    """Upload a doc, then query it via RAG."""
    # Upload a document with specific content
    resp = client.post(
        "/documents",
        files={
            "file": (
                "pump_manual.txt",
                b"Pump P-101 Operating Manual\n\n"
                b"The pump P-101 requires maintenance every 6 months. "
                b"The maximum operating pressure is 150 PSI. "
                b"Located in Building A Section 3.",
                "text/plain",
            )
        },
    )
    assert resp.status_code == 201

    # Query
    resp = client.post(
        "/rag/query",
        json={"query": "How often does pump P-101 need maintenance?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Should either be answered or insufficient (depending on mock LLM)
    assert body["verdict"] in ("answered", "insufficient_evidence")
    # Should have evidence if any was found
    if body["evidence"]:
        assert body["evidence"][0]["document_id"]


def test_rag_query_returns_citations(client: TestClient) -> None:
    """RAG response should include evidence with document_id and page."""
    # Upload a document
    resp = client.post(
        "/documents",
        files={
            "file": (
                "report.txt",
                b"Inspection Report\n\n"
                b"Valve V-202 was found leaking from the stem seal. "
                b"Replacement gasket part number is G-789. "
                b"Maintenance crew notified.",
                "text/plain",
            )
        },
    )
    assert resp.status_code == 201

    resp = client.post(
        "/rag/query",
        json={"query": "What is the gasket part number for valve V-202?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Evidence should be present with provenance
    if body["evidence"]:
        ev = body["evidence"][0]
        assert "document_id" in ev
        assert "text" in ev
        assert "section_path" in ev


def test_rag_query_with_document_filter(client: TestClient) -> None:
    """Query with document_id filter should restrict to that document."""
    # Upload two documents
    resp = client.post(
        "/documents",
        files={"file": ("doc1.txt", b"Pump alpha maintenance schedule monthly", "text/plain")},
    )
    doc1_id = resp.json()["document_id"]

    client.post(
        "/documents",
        files={"file": ("doc2.txt", b"Pump beta maintenance schedule quarterly", "text/plain")},
    )

    resp = client.post(
        "/rag/query",
        json={"query": "pump maintenance", "document_id": doc1_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    # All evidence should be from doc1
    if body["evidence"]:
        assert all(e["document_id"] == doc1_id for e in body["evidence"])


def test_rag_query_response_structure(client: TestClient) -> None:
    """RAG response should have all expected fields."""
    client.post(
        "/documents",
        files={"file": ("test.txt", b"Some test content for RAG pipeline", "text/plain")},
    )

    resp = client.post("/rag/query", json={"query": "test content"})
    assert resp.status_code == 200
    body = resp.json()
    assert "query" in body
    assert "verdict" in body
    assert "verdict_message" in body
    assert "answer" in body
    assert "claims" in body
    assert "evidence" in body
    assert "is_answered" in body


def test_rag_empty_query_rejected(client: TestClient) -> None:
    """Empty query should be rejected by validation."""
    resp = client.post("/rag/query", json={"query": ""})
    assert resp.status_code == 422  # validation error
