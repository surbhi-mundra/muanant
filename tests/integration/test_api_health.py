"""Integration test: API health endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.app import create_app
from sovereign.core.config import reset_settings_cache
from sovereign.models.gateway import reset_model_gateway
from sovereign.storage.db.base import init_schema, reset_engine


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")

    reset_settings_cache()
    reset_model_gateway()
    reset_engine()
    init_schema()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_engine()
    reset_model_gateway()
    reset_settings_cache()


def test_root_endpoint(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "SOVEREIGN"
    assert "version" in body
    assert body["env"] == "dev"


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_readyz_returns_ok_when_deps_available(client: TestClient) -> None:
    """readyz must return 200 when DB + ModelGateway are reachable."""
    r = client.get("/readyz")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "database" in body["checks"]
    assert body["checks"]["database"].startswith("ok")
    assert "model_gateway" in body["checks"]
    assert "mock" in body["checks"]["model_gateway"]


def test_request_id_header_returned(client: TestClient) -> None:
    """X-Request-ID must be returned on every response."""
    r = client.get("/healthz")
    assert "x-request-id" in r.headers
    assert r.headers["x-request-id"].startswith("req_")


def test_request_id_echoed_when_provided(client: TestClient) -> None:
    """If client sends X-Request-ID, server must echo the same value."""
    custom = "my-trace-id-12345"
    r = client.get("/healthz", headers={"X-Request-ID": custom})
    assert r.headers["x-request-id"] == custom


def test_openapi_available_in_dev(client: TestClient) -> None:
    """OpenAPI spec must be served in dev for the docs UI."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "SOVEREIGN"
    assert "/healthz" in spec["paths"]
    assert "/readyz" in spec["paths"]
