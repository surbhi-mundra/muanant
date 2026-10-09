"""Tests for sovereign.models — ModelGateway + MockBackend."""

from __future__ import annotations

import pytest

from sovereign.models.backends import registered_backends
from sovereign.models.backends.mock import (
    MockEmbeddingModel,
    MockOCR,
    MockReranker,
    MockTextLLM,
    MockVisionLLM,
)
from sovereign.models.gateway import ModelGateway, get_model_gateway, reset_model_gateway
from sovereign.models.schemas import (
    OCR,
    EmbeddingModel,
    EmbeddingRequest,
    ImageInput,
    LLMRequest,
    Message,
    OCRRequest,
    RerankCandidate,
    Reranker,
    RerankRequest,
    TextLLM,
    VisionLLM,
    VisionRequest,
)


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------
def test_mock_backends_registered() -> None:
    """All 5 mock backends must be in the registry."""
    names = registered_backends()
    assert "mock.text" in names
    assert "mock.vision" in names
    assert "mock.embedding" in names
    assert "mock.reranker" in names
    assert "mock.ocr" in names


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------
def test_mock_text_llm_satisfies_protocol() -> None:
    m = MockTextLLM()
    assert isinstance(m, TextLLM)


def test_mock_vision_llm_satisfies_protocol() -> None:
    m = MockVisionLLM()
    assert isinstance(m, VisionLLM)


def test_mock_embedding_satisfies_protocol() -> None:
    m = MockEmbeddingModel()
    assert isinstance(m, EmbeddingModel)
    assert m.dim == 384


def test_mock_reranker_satisfies_protocol() -> None:
    m = MockReranker()
    assert isinstance(m, Reranker)


def test_mock_ocr_satisfies_protocol() -> None:
    m = MockOCR()
    assert isinstance(m, OCR)


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------
async def test_mock_text_llm_returns_echo() -> None:
    llm = MockTextLLM()
    resp = await llm.complete(LLMRequest(messages=[Message(role="user", content="hello")]))
    assert "hello" in resp.content
    assert resp.model == "mock-text-llm"
    assert resp.finish_reason == "stop"


async def test_mock_text_llm_tool_call_trigger() -> None:
    llm = MockTextLLM()
    resp = await llm.complete(
        LLMRequest(messages=[Message(role="user", content="please call tool_call:search_kb")])
    )
    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search_kb"


async def test_mock_text_llm_json_mode() -> None:
    llm = MockTextLLM()
    resp = await llm.complete(
        LLMRequest(messages=[Message(role="user", content="x")], json_mode=True)
    )
    import json

    parsed = json.loads(resp.content)
    assert "answer" in parsed
    assert parsed["mock"] is True


async def test_mock_embeddings_are_deterministic() -> None:
    """Same text → same vector (essential for retrieval stability in tests)."""
    emb = MockEmbeddingModel(dim=64)
    r1 = await emb.embed(EmbeddingRequest(texts=["hello world"]))
    r2 = await emb.embed(EmbeddingRequest(texts=["hello world"]))
    assert r1.vectors[0] == r2.vectors[0]
    assert r1.dim == 64


async def test_mock_embeddings_different_for_different_text() -> None:
    emb = MockEmbeddingModel(dim=64)
    r = await emb.embed(EmbeddingRequest(texts=["hello world", "goodbye world"]))
    assert r.vectors[0] != r.vectors[1]


async def test_mock_embeddings_normalized() -> None:
    """Normalized embeddings must have L2 norm ~1.0."""
    emb = MockEmbeddingModel(dim=64)
    r = await emb.embed(EmbeddingRequest(texts=["test"], normalize=True))
    norm = sum(x * x for x in r.vectors[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


async def test_mock_reranker_orders_by_overlap() -> None:
    """Reranker should score higher for candidates with more query overlap."""
    rr = MockReranker()
    r = await rr.rerank(
        RerankRequest(
            query="error in pump",
            candidates=[
                RerankCandidate(doc_id="a", text="the pump has an error"),
                RerankCandidate(doc_id="b", text="the weather is sunny"),
                RerankCandidate(doc_id="c", text="pump maintenance schedule"),
            ],
        )
    )
    assert r.ranked[0].doc_id == "a"
    assert r.ranked[0].score > r.ranked[1].score


async def test_mock_reranker_respects_top_k() -> None:
    rr = MockReranker()
    r = await rr.rerank(
        RerankRequest(
            query="test",
            candidates=[RerankCandidate(doc_id=str(i), text=f"test {i}") for i in range(10)],
            top_k=3,
        )
    )
    assert len(r.ranked) == 3


async def test_mock_ocr_returns_placeholder() -> None:
    ocr = MockOCR()
    r = await ocr.recognize(OCRRequest(image=ImageInput(data=b"fake")))
    assert r.text
    assert r.lines
    assert r.blocks
    assert r.confidence > 0.5


async def test_mock_vision_describes_image() -> None:
    v = MockVisionLLM()
    r = await v.describe(
        VisionRequest(images=[ImageInput(data=b"fake")], prompt="what is this?")
    )
    assert "1 image" in r.text
    assert "what is this?" in r.text


# ---------------------------------------------------------------------------
# ModelGateway
# ---------------------------------------------------------------------------
@pytest.fixture
def gateway() -> ModelGateway:
    reset_model_gateway()
    return get_model_gateway()


def test_gateway_provides_all_capabilities(gateway: ModelGateway) -> None:
    """All 5 properties must return instances satisfying their protocols."""
    assert isinstance(gateway.text, TextLLM)
    assert isinstance(gateway.vision, VisionLLM)
    assert isinstance(gateway.embedding, EmbeddingModel)
    assert isinstance(gateway.reranker, Reranker)
    assert isinstance(gateway.ocr, OCR)


def test_gateway_describe_lists_all_backends(gateway: ModelGateway) -> None:
    """describe() must return all 5 capabilities with their backend names."""
    d = gateway.describe()
    assert set(d.keys()) == {"text", "vision", "embedding", "reranker", "ocr"}
    assert all(v.startswith("mock.") for v in d.values())


def test_gateway_lazy_construction(gateway: ModelGateway) -> None:
    """Backends must not be constructed until first access."""
    # Before accessing any property, internal fields are None.
    assert gateway._text is None
    assert gateway._vision is None
    _ = gateway.text
    assert gateway._text is not None
    assert gateway._vision is None  # still not constructed


def test_gateway_rejects_missing_backend() -> None:
    """A GatewayConfig with an unknown backend must raise on access."""
    from sovereign.core.errors import ModelUnavailableError
    from sovereign.models.gateway import GatewayConfig

    bad_cfg = GatewayConfig(
        text={"backend": "nonexistent.text"},
        vision={"backend": "mock.vision"},
        embedding={"backend": "mock.embedding"},
        reranker={"backend": "mock.reranker"},
        ocr={"backend": "mock.ocr"},
    )
    gw = ModelGateway(bad_cfg)
    with pytest.raises(ModelUnavailableError):
        _ = gw.text
