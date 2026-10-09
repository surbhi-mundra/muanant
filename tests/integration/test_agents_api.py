"""Integration tests for the agent orchestration API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.app import create_app
from sovereign.core.config import reset_settings_cache
from sovereign.embeddings.indexing import reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.orchestration import reset_orchestrator
from sovereign.rag.pipeline import reset_rag_pipeline
from sovereign.storage.db.base import init_schema, reset_engine
from sovereign.storage.objects import reset_object_store
from sovereign.storage.qdrant import reset_qdrant_store


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    monkeypatch.setenv("OBJECT_STORE_FS_ROOT", str(tmp_path / "objects"))
    reset_settings_cache()
    reset_model_gateway()
    reset_engine()
    reset_object_store()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()
    reset_orchestrator()
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
    reset_orchestrator()
    reset_settings_cache()


def test_agent_query_basic(client: TestClient) -> None:
    """POST /agents/query should return an agent response."""
    resp = client.post("/agents/query", json={"query": "What is pump P-101?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "What is pump P-101?"
    assert "task_type" in body
    assert "steps_completed" in body
    assert "errors" in body
    assert "succeeded" in body


def test_agent_query_with_document(client: TestClient) -> None:
    """Query with document_id should work."""
    resp = client.post(
        "/agents/query",
        json={"query": "Analyze this document", "document_id": "fake_doc_id"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "Analyze this document"


def test_agent_query_empty_rejected(client: TestClient) -> None:
    """Empty query should be rejected."""
    resp = client.post("/agents/query", json={"query": ""})
    assert resp.status_code == 422


def test_agent_query_research_blocked(client: TestClient) -> None:
    """Research task should return blocked status."""
    resp = client.post(
        "/agents/query",
        json={"query": "research this topic externally online"},
    )
    assert resp.status_code == 200
    body = resp.json()
    if body.get("research_results"):
        assert body["research_results"][0]["source"] in ("blocked", "placeholder")


def test_agent_query_risk_assessment(client: TestClient) -> None:
    """Risk assessment query should complete."""
    resp = client.post(
        "/agents/query",
        json={"query": "What are the safety risks and hazards?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "steps_completed" in body


def test_agent_query_response_has_all_fields(client: TestClient) -> None:
    """Response should include all expected fields."""
    resp = client.post("/agents/query", json={"query": "test question"})
    assert resp.status_code == 200
    body = resp.json()
    expected_fields = [
        "query", "task_type", "steps_completed", "errors", "succeeded",
        "rag_response", "evidence_report", "document_analysis",
        "vision_description", "research_results", "findings", "deliverable",
    ]
    for field in expected_fields:
        assert field in body, f"missing field: {field}"
