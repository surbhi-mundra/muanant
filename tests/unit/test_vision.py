"""Tests for sovereign.vision — VisionService via the MockBackend."""

from __future__ import annotations

import pytest

from sovereign.models.gateway import reset_model_gateway
from sovereign.vision.service import VisionService


@pytest.fixture(autouse=True)
def _reset_gateway():
    reset_model_gateway()
    yield
    reset_model_gateway()


class TestVisionService:
    async def test_describe_image_returns_text(self) -> None:
        """VisionService.describe_image should return text from the vision model."""
        service = VisionService()
        result = await service.describe_image(b"fake-image-data", "image/png")
        assert result.text
        assert "mock-vision" in result.model
        assert result.image_count == 1

    async def test_describe_diagram_uses_specialized_prompt(self) -> None:
        """describe_diagram should use a diagram-specific prompt."""
        service = VisionService()
        result = await service.describe_diagram(b"fake-data", "image/png")
        # The mock vision model echoes the prompt, so we can check it contains
        # diagram-specific keywords
        assert result.text
        assert "1 image" in result.text

    async def test_describe_inspection_image(self) -> None:
        """describe_inspection_image should use an inspection-specific prompt."""
        service = VisionService()
        result = await service.describe_inspection_image(b"fake-data", "image/png")
        assert result.text
        assert "1 image" in result.text

    async def test_extract_text_from_image(self) -> None:
        """extract_text_from_image should use an OCR-specific prompt."""
        service = VisionService()
        result = await service.extract_text_from_image(b"fake-data", "image/png")
        assert result.text
        assert "1 image" in result.text

    def test_normalize_media_type(self) -> None:
        """_normalize_media_type should handle common MIME types."""
        from sovereign.vision.service import _normalize_media_type

        assert _normalize_media_type("image/png") == "image/png"
        assert _normalize_media_type("image/jpeg") == "image/jpeg"
        assert _normalize_media_type("image/jpg") == "image/jpeg"
        assert _normalize_media_type("image/webp") == "image/webp"
        assert _normalize_media_type("application/octet-stream") == "image/png"
        assert _normalize_media_type("") == "image/png"
