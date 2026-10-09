"""Integration smoke test: full gateway + audit round-trip."""

from __future__ import annotations

import pytest

from sovereign.audit.chain import AuditEventPayload
from sovereign.audit.log import verify_full_chain, write_event
from sovereign.models.gateway import get_model_gateway, reset_model_gateway
from sovereign.models.schemas import (
    EmbeddingRequest,
    ImageInput,
    LLMRequest,
    Message,
    OCRRequest,
    RerankCandidate,
    RerankRequest,
    VisionRequest,
)
from sovereign.storage.db.base import init_schema, reset_engine, session_scope


@pytest.fixture(autouse=True)
def _fresh_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    from sovereign.core.config import reset_settings_cache

    reset_settings_cache()
    reset_engine()
    reset_model_gateway()
    init_schema()
    yield
    reset_engine()
    reset_model_gateway()
    reset_settings_cache()


async def test_full_smoke_text_then_audit() -> None:
    """End-to-end: call the gateway, then write an audit event, then verify chain."""
    gw = get_model_gateway()

    # 1. LLM call
    resp = await gw.text.complete(
        LLMRequest(messages=[Message(role="user", content="hello sovereign")])
    )
    assert resp.content

    # 2. Embedding
    emb = await gw.embedding.embed(EmbeddingRequest(texts=["hello"]))
    assert emb.dim > 0
    assert len(emb.vectors) == 1

    # 3. Rerank
    rr = await gw.reranker.rerank(
        RerankRequest(
            query="hello",
            candidates=[RerankCandidate(doc_id="1", text="hello world")],
        )
    )
    assert len(rr.ranked) == 1

    # 4. Vision
    v = await gw.vision.describe(
        VisionRequest(images=[ImageInput(data=b"x")], prompt="describe")
    )
    assert v.text

    # 5. OCR
    o = await gw.ocr.recognize(OCRRequest(image=ImageInput(data=b"x")))
    assert o.text

    # 6. Audit
    with session_scope() as s:
        for i in range(3):
            write_event(
                s,
                AuditEventPayload(
                    category="agent",
                    action="llm.complete",
                    outcome="success",
                    model=resp.model,
                    prompt_tokens=resp.usage.prompt_tokens,
                    completion_tokens=resp.usage.completion_tokens,
                    details={"iteration": i},
                ),
            )

    # 7. Verify chain
    with session_scope() as s:
        assert verify_full_chain(s) is True
