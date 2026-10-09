"""Vision service — multimodal processing via the VisionLLM protocol.

This module provides:
- Image description (what's in this image?)
- Diagram/figure understanding (engineering drawings, charts, schematics)
- Figure captioning for extracted images from documents

The vision service uses the ``VisionLLM`` protocol from the ModelGateway,
so it works with the MockBackend in dev and real vision models (Qwen2-VL,
Llama-3.2-Vision, etc.) in prod — selected via ``configs/models.yaml``.

Security note: images are DATA, not instructions. Vision model output is
always treated as data and injected into downstream LLM context as
``tool``/``user`` role, never ``system`` (per ADR 0003).
"""

from __future__ import annotations

from dataclasses import dataclass

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway, get_model_gateway
from sovereign.models.schemas import ImageInput, VisionRequest

log = get_logger(__name__)


@dataclass
class VisionDescription:
    """Result of a vision model call."""

    text: str
    model: str
    image_count: int


class VisionService:
    """High-level vision operations using the ModelGateway's VisionLLM."""

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    async def describe_image(
        self,
        image_data: bytes,
        media_type: str = "image/png",
        prompt: str = (
            "Describe what you see in this image. Focus on any text, "
            "diagrams, equipment, or technical details."
        ),
    ) -> VisionDescription:
        """Describe a single image using the vision model."""
        req = VisionRequest(
            images=[ImageInput(data=image_data, media_type=_normalize_media_type(media_type))],  # type: ignore[arg-type]
            prompt=prompt,
        )
        resp = await self.gateway.vision.describe(req)
        return VisionDescription(
            text=resp.text,
            model=resp.model,
            image_count=1,
        )

    async def describe_diagram(
        self,
        image_data: bytes,
        media_type: str = "image/png",
    ) -> VisionDescription:
        """Describe an engineering diagram or schematic.

        Uses a specialized prompt for technical diagrams: P&IDs, electrical
        schematics, flow charts, equipment layouts.
        """
        prompt = (
            "This is an engineering diagram or schematic. Describe:\n"
            "1. The type of diagram (P&ID, electrical, mechanical, flow chart, etc.)\n"
            "2. All visible equipment and components (with labels/tags if present)\n"
            "3. All visible text and annotations\n"
            "4. Connections and relationships between components\n"
            "5. Any measurements, ratings, or specifications shown\n"
            "Be precise and technical. If you cannot read a label, say so."
        )
        return await self.describe_image(image_data, media_type, prompt)

    async def describe_inspection_image(
        self,
        image_data: bytes,
        media_type: str = "image/png",
    ) -> VisionDescription:
        """Describe an inspection photo (equipment, damage, condition)."""
        prompt = (
            "This is an industrial inspection photograph. Describe:\n"
            "1. The equipment or structure shown\n"
            "2. Its general condition (new, aged, damaged, corroded, etc.)\n"
            "3. Any visible defects, wear, or anomalies\n"
            "4. Any visible labels, tags, or markings\n"
            "5. The environment/context (indoor, outdoor, operating, shutdown)\n"
            "Be objective and specific. Note both normal and abnormal findings."
        )
        return await self.describe_image(image_data, media_type, prompt)

    async def extract_text_from_image(
        self,
        image_data: bytes,
        media_type: str = "image/png",
    ) -> VisionDescription:
        """Extract all visible text from an image (vision-based OCR)."""
        prompt = (
            "Extract ALL visible text from this image. Output the text exactly as "
            "it appears, preserving line breaks. If there are tables, format them "
            "as markdown tables. If there is no text, say 'No text found.'"
        )
        return await self.describe_image(image_data, media_type, prompt)


def _normalize_media_type(media_type: str) -> str:
    """Normalize a media type string to the VisionLLM-accepted set."""
    mt = media_type.lower().strip()
    if "png" in mt:
        return "image/png"
    if "jpeg" in mt or "jpg" in mt:
        return "image/jpeg"
    if "webp" in mt:
        return "image/webp"
    return "image/png"  # default
