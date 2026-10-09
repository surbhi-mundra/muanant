"""Request/response schemas for the ModelGateway.

These are intentionally minimal — they capture only what every backend can
satisfy. Backend-specific options (vLLM sampling params, Ollama format hints,
etc.) go in an ``options: dict`` field so the protocol stays stable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------
Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str
    # For role="tool": the tool name that produced this content.
    # For role="assistant" with tool_calls: the call IDs this message answers.
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON-encoded arguments


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class EvidenceSpan:
    """Optional: backend can return per-token evidence spans (e.g. ColPali)."""

    start: int
    end: int
    score: float = 0.0


# ---------------------------------------------------------------------------
# Text LLM
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LLMRequest:
    messages: list[Message]
    model: str | None = None  # None = gateway default
    temperature: float = 0.0
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: Literal["auto", "none", "required"] | dict[str, Any] = "auto"
    json_mode: bool = False
    stop: list[str] | None = None
    # Backend-specific passthrough. Avoid unless necessary.
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] = "stop"
    model: str = ""
    # Backend should echo the request model alias for audit.
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMStreamChunk:
    content_delta: str = ""
    tool_calls_delta: list[ToolCall] = field(default_factory=list)
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None


# ---------------------------------------------------------------------------
# Vision LLM
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ImageInput:
    """A single image submitted to a vision model.

    Either ``data`` (raw bytes) or ``path`` (filesystem path) must be set.
    Backends decide which they consume; both are passed when available.
    """

    data: bytes | None = None
    path: str | None = None
    media_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"


@dataclass(slots=True)
class VisionRequest:
    images: list[ImageInput]
    prompt: str
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None


@dataclass(slots=True)
class VisionResponse:
    text: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class EmbeddingRequest:
    texts: list[str]
    model: str | None = None
    normalize: bool = True
    batch_size: int | None = None


@dataclass(slots=True)
class EmbeddingResponse:
    vectors: list[list[float]]
    dim: int
    model: str


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class RerankCandidate:
    """A retrieval candidate to be reranked.

    ``doc_id`` and ``text`` are the minimum; metadata is opaque and returned
    unchanged on the scored candidate so callers can round-trip provenance.
    """

    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScoredCandidate:
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RerankRequest:
    query: str
    candidates: list[RerankCandidate]
    top_k: int | None = None
    model: str | None = None


@dataclass(slots=True)
class RerankResponse:
    ranked: list[ScoredCandidate]
    model: str


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class OCRRequest:
    image: ImageInput
    # Optional: hint about expected language(s), e.g. ["eng", "deu"].
    languages: list[str] = field(default_factory=lambda: ["eng"])
    # Optional: request layout/structure info (boxes, reading order).
    with_layout: bool = False


@dataclass(slots=True)
class OCRWord:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in pixels
    confidence: float


@dataclass(slots=True)
class OCRLine:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    words: list[OCRWord] = field(default_factory=list)


@dataclass(slots=True)
class OCRBlock:
    """A layout block — paragraph, table cell, figure caption, etc."""

    kind: Literal["text", "title", "caption", "table", "figure", "list"]
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    lines: list[OCRLine] = field(default_factory=list)


@dataclass(slots=True)
class OCRResult:
    text: str
    lines: list[OCRLine] = field(default_factory=list)
    blocks: list[OCRBlock] = field(default_factory=list)
    confidence: float = 0.0
    model: str = ""
    page_size: tuple[int, int] = (0, 0)  # width, height in pixels


# ---------------------------------------------------------------------------
# Protocols (the contract surface)
# ---------------------------------------------------------------------------
@runtime_checkable
class TextLLM(Protocol):
    """Synchronous + streaming text completion."""

    @property
    def model_name(self) -> str: ...

    async def complete(self, req: LLMRequest) -> LLMResponse: ...

    def stream(self, req: LLMRequest) -> AsyncIterator[LLMStreamChunk]: ...


@runtime_checkable
class VisionLLM(Protocol):
    @property
    def model_name(self) -> str: ...

    async def describe(self, req: VisionRequest) -> VisionResponse: ...


@runtime_checkable
class EmbeddingModel(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse: ...


@runtime_checkable
class Reranker(Protocol):
    @property
    def model_name(self) -> str: ...

    async def rerank(self, req: RerankRequest) -> RerankResponse: ...


@runtime_checkable
class OCR(Protocol):
    @property
    def model_name(self) -> str: ...

    async def recognize(self, req: OCRRequest) -> OCRResult: ...
