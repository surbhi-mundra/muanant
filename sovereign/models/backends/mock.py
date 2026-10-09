"""MockBackend — recorded-fixture model backend for dev/CI.

This is the *only* backend the dev sandbox uses. It runs on CPU with zero ML
dependencies and returns deterministic, fixture-driven responses. Real
backends (vLLM, Ollama, sentence-transformers, Tesseract, Surya) are loaded
on GPU tiers via ``configs/models.yaml`` and implement the same protocols.

The MockBackend serves three purposes:
1. Lets the entire pipeline run on a CPU-only dev box.
2. Provides deterministic inputs for tests.
3. Documents the protocol contract by being a reference implementation.

It is NOT a fake — it returns real, well-typed responses. It just doesn't
call a real model. Production systems swap it out by editing YAML, not code.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sovereign.models.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    ImageInput,  # noqa: F401  (re-exported for tests)
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    OCRBlock,
    OCRLine,
    OCRRequest,
    OCRResult,
    OCRWord,
    RerankRequest,
    RerankResponse,
    ScoredCandidate,
    ToolCall,
    Usage,
    VisionRequest,
    VisionResponse,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "models"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture from tests/fixtures/models/.

    Falls back to a synthetic response if the fixture file is missing —
    that keeps tests runnable even before fixtures are committed.
    """
    path = _FIXTURES_DIR / f"{name}.json"
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


# ---------------------------------------------------------------------------
# Mock TextLLM
# ---------------------------------------------------------------------------
class MockTextLLM:
    """Returns deterministic completions.

    Behavior:
    - If the last user message contains "tool_call:<name>", returns a
      tool_calls response with that name and empty args.
    - If ``json_mode`` is True, wraps the response in a JSON object.
    - Otherwise returns a short, deterministic echo of the prompt.
    """

    def __init__(self, model_name: str = "mock-text-llm") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def complete(self, req: LLMRequest) -> LLMResponse:
        last_user = next(
            (m.content for m in reversed(req.messages) if m.role == "user"),
            "",
        )

        # Tool-call trigger for tests
        if "tool_call:" in last_user:
            _, tool_name = last_user.split("tool_call:", 1)
            tool_name = tool_name.strip() or "default_tool"
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="call_mock_1", name=tool_name, arguments="{}")],
                usage=Usage(prompt_tokens=len(last_user) // 4, completion_tokens=8),
                finish_reason="tool_calls",
                model=self._model_name,
            )

        # JSON mode
        content = f"[mock] {last_user[:200]}"
        if req.json_mode:
            content = json.dumps({"answer": content, "mock": True})

        return LLMResponse(
            content=content,
            usage=Usage(prompt_tokens=len(last_user) // 4, completion_tokens=len(content) // 4),
            finish_reason="stop",
            model=self._model_name,
        )

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        # Token-by-token mock stream.
        resp = await self.complete(req)
        tokens = resp.content.split()
        for tok in tokens:
            yield LLMStreamChunk(content_delta=tok + " ")
        yield LLMStreamChunk(finish_reason="stop")


# ---------------------------------------------------------------------------
# Mock VisionLLM
# ---------------------------------------------------------------------------
class MockVisionLLM:
    def __init__(self, model_name: str = "mock-vision-llm") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def describe(self, req: VisionRequest) -> VisionResponse:
        n_images = len(req.images)
        text = f"[mock-vision] Saw {n_images} image(s). Prompt: {req.prompt[:100]}"
        return VisionResponse(
            text=text,
            usage=Usage(prompt_tokens=len(req.prompt) // 4, completion_tokens=len(text) // 4),
            model=self._model_name,
        )


# ---------------------------------------------------------------------------
# Mock EmbeddingModel
# ---------------------------------------------------------------------------
class MockEmbeddingModel:
    """Deterministic hash-based embeddings.

    Same input → same vector. Dim configurable (default 384 to match
    sentence-transformers/all-MiniLM-L6-v2, so swapping to a real model
    doesn't change the Qdrant collection config).
    """

    def __init__(self, dim: int = 384, model_name: str = "mock-embeddings") -> None:
        self._dim = dim
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse:
        vectors: list[list[float]] = []
        for text in req.texts:
            # Hash text repeatedly to fill the vector, then normalize.
            v: list[float] = []
            counter = 0
            while len(v) < self._dim:
                digest = hashlib.sha256(f"{text}|{counter}".encode()).digest()
                for b in digest:
                    v.append((b - 128) / 128.0)
                    if len(v) >= self._dim:
                        break
                counter += 1
            if req.normalize:
                norm = sum(x * x for x in v) ** 0.5 or 1.0
                v = [x / norm for x in v]
            vectors.append(v)
        return EmbeddingResponse(vectors=vectors, dim=self._dim, model=self._model_name)


# ---------------------------------------------------------------------------
# Mock Reranker
# ---------------------------------------------------------------------------
class MockReranker:
    """Reranks by cheap lexical overlap (Jaccard on whitespace tokens).

    Not as good as a cross-encoder, but deterministic and good enough for
    pipeline tests. Real deployments use ``cross_encoder.CrossEncoderReranker``.
    """

    def __init__(self, model_name: str = "mock-reranker") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def rerank(self, req: RerankRequest) -> RerankResponse:
        q_tokens = set(req.query.lower().split())
        scored: list[ScoredCandidate] = []
        for c in req.candidates:
            c_tokens = set(c.text.lower().split())
            if not q_tokens or not c_tokens:
                score = 0.0
            else:
                score = len(q_tokens & c_tokens) / len(q_tokens | c_tokens)
            scored.append(
                ScoredCandidate(
                    doc_id=c.doc_id, text=c.text, score=score, metadata=c.metadata
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        if req.top_k is not None:
            scored = scored[: req.top_k]
        return RerankResponse(ranked=scored, model=self._model_name)


# ---------------------------------------------------------------------------
# Mock OCR
# ---------------------------------------------------------------------------
class MockOCR:
    """Returns a synthetic OCR result with one line and one block.

    Real OCR engines return actual text from the image; the mock returns
    placeholder text so the pipeline can be exercised end-to-end on CPU.
    """

    def __init__(self, model_name: str = "mock-ocr") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def recognize(self, req: OCRRequest) -> OCRResult:
        line = OCRLine(
            text="[mock-ocr] placeholder text",
            bbox=(0.0, 0.0, 100.0, 20.0),
            confidence=0.95,
            words=[
                OCRWord(text="[mock-ocr]", bbox=(0.0, 0.0, 40.0, 20.0), confidence=0.97),
                OCRWord(text="placeholder", bbox=(42.0, 0.0, 75.0, 20.0), confidence=0.94),
                OCRWord(text="text", bbox=(77.0, 0.0, 100.0, 20.0), confidence=0.93),
            ],
        )
        block = OCRBlock(
            kind="text",
            text=line.text,
            bbox=line.bbox,
            confidence=0.95,
            lines=[line],
        )
        return OCRResult(
            text=line.text,
            lines=[line],
            blocks=[block],
            confidence=0.95,
            model=self._model_name,
            page_size=(100, 20),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_mock_backend() -> dict[str, Any]:
    """Return a complete mock backend dict, keyed by capability."""
    return {
        "text": MockTextLLM(),
        "vision": MockVisionLLM(),
        "embedding": MockEmbeddingModel(),
        "reranker": MockReranker(),
        "ocr": MockOCR(),
    }
