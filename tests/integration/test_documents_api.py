"""Integration tests for the documents API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.app import create_app
from sovereign.core.config import reset_settings_cache
from sovereign.models.gateway import reset_model_gateway
from sovereign.storage.db.base import init_schema, reset_engine
from sovereign.storage.objects import reset_object_store


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    monkeypatch.setenv("OBJECT_STORE_FS_ROOT", str(tmp_path / "objects"))
    reset_settings_cache()
    reset_model_gateway()
    reset_engine()
    reset_object_store()
    init_schema()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_engine()
    reset_model_gateway()
    reset_object_store()
    reset_settings_cache()


def test_upload_txt_via_api(client: TestClient) -> None:
    """Upload a TXT file via the API and verify it's stored."""
    resp = client.post(
        "/documents",
        files={"file": ("test.txt", b"Hello SOVEREIGN world.", "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "parsed"
    assert body["document_id"]
    assert body["mime_type"] == "text/plain"
    assert body["version"] == 1


def test_upload_and_list(client: TestClient) -> None:
    """Upload then list should show the document."""
    client.post(
        "/documents",
        files={"file": ("doc1.txt", b"First document content", "text/plain")},
    )
    client.post(
        "/documents",
        files={"file": ("doc2.txt", b"Second document content", "text/plain")},
    )
    resp = client.get("/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


def test_upload_and_get_by_id(client: TestClient) -> None:
    """Upload then GET /{id} should return metadata."""
    resp = client.post(
        "/documents",
        files={"file": ("test.txt", b"Get me by ID", "text/plain")},
    )
    doc_id = resp.json()["document_id"]
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == doc_id
    assert body["original_filename"] == "test.txt"


def test_upload_and_get_parsed(client: TestClient) -> None:
    """Upload then GET /{id}/parsed should return the ParsedDocument."""
    resp = client.post(
        "/documents",
        files={"file": ("test.txt", b"Parse this content", "text/plain")},
    )
    doc_id = resp.json()["document_id"]
    resp = client.get(f"/documents/{doc_id}/parsed")
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["source_filename"] == "test.txt"
    assert len(parsed["pages"]) >= 1


def test_upload_and_delete(client: TestClient) -> None:
    """Upload then DELETE should remove the document."""
    resp = client.post(
        "/documents",
        files={"file": ("test.txt", b"Delete me", "text/plain")},
    )
    doc_id = resp.json()["document_id"]
    resp = client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 204
    # Verify it's gone
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 404


def test_get_missing_returns_404(client: TestClient) -> None:
    """Getting a non-existent document should return 404."""
    resp = client.get("/documents/nonexistent_id")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "sovereign.not_found"


def test_upload_duplicate(client: TestClient) -> None:
    """Uploading the same content twice should return duplicate status."""
    content = b"Duplicate content test"
    client.post("/documents", files={"file": ("a.txt", content, "text/plain")})
    resp = client.post(
        "/documents", files={"file": ("b.txt", content, "text/plain")}
    )
    assert resp.status_code == 200  # duplicate = 200, not 201
    body = resp.json()
    assert body["is_duplicate"] is True
    assert body["status"] == "duplicate"


def test_upload_empty_quarantines(client: TestClient) -> None:
    """Empty file should be quarantined."""
    resp = client.post(
        "/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "quarantined"


def test_upload_image_via_api(client: TestClient) -> None:
    """Upload a PNG image — should be OCR'd and stored."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "TEST OCR TEXT 12345", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_data = buf.getvalue()

    resp = client.post(
        "/documents",
        files={"file": ("test.png", image_data, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "parsed"
    assert body["mime_type"] == "image/png"
    assert body["document_id"]


def test_vision_describe_endpoint(client: TestClient) -> None:
    """POST /vision/describe should return a description."""
    # Create a minimal PNG
    import io

    from PIL import Image

    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    resp = client.post(
        "/vision/describe",
        files={"file": ("test.png", buf.getvalue(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"]
    assert "mock-vision" in body["model"]


def test_ocr_image_endpoint(client: TestClient) -> None:
    """POST /ocr/image should run OCR and return text."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "OCR TEST 67890", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    resp = client.post(
        "/ocr/image",
        files={"file": ("test.png", buf.getvalue(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"]  # should have some text from OCR
    assert "tesseract" in body["model"]
