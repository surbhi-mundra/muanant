"""Ollama adapter — real local LLM inference via Ollama.

Works on Mac (Apple Silicon + Intel), Linux, and Windows.
Install Ollama: https://ollama.com

Pull models:
    ollama pull qwen2.5:7b-instruct
    ollama pull qwen2.5:3b-instruct   (lighter, faster)

Satisfies the TextLLM protocol from sovereign.models.schemas.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from sovereign.core.logging import get_logger
from sovereign.models.schemas import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    Usage,
)

log = get_logger(__name__)


class OllamaTextLLM:
    """Real text LLM via Ollama.

    Implements the TextLLM protocol.
    """

    def __init__(
        self,
        model_name: str = "qwen2.5:7b-instruct",
        server_url: str = "http://127.0.0.1:11434",
    ) -> None:
        self._model_name = model_name
        self._server_url = server_url.rstrip("/")

    @property
    def model_name(self) -> str:
        return self._model_name

    async def complete(self, req: LLMRequest) -> LLMResponse:
        """Call Ollama's /api/chat endpoint."""
        model = req.model or self._model_name

        # Convert messages to Ollama format
        ollama_messages: list[dict[str, str]] = []
        for msg in req.messages:
            ollama_messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": req.temperature,
            },
        }

        if req.max_tokens:
            payload["options"]["num_predict"] = req.max_tokens

        if req.stop:
            payload["options"]["stop"] = req.stop

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._server_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count", 0)
            prompt_count = data.get("prompt_eval_count", 0)

            return LLMResponse(
                content=content,
                usage=Usage(
                    prompt_tokens=prompt_count,
                    completion_tokens=eval_count,
                    total_tokens=prompt_count + eval_count,
                ),
                finish_reason="stop",
                model=model,
            )

        except Exception as e:
            log.error("ollama.complete.failed", error=str(e))
            return LLMResponse(
                content=f"[Ollama error: {e}]",
                finish_reason="stop",
                model=model,
            )

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Stream completion from Ollama."""
        model = req.model or self._model_name

        ollama_messages: list[dict[str, str]] = []
        for msg in req.messages:
            ollama_messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": req.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client, client.stream(
            "POST",
            f"{self._server_url}/api/chat",
            json=payload,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield LLMStreamChunk(content_delta=content)
                    if data.get("done"):
                        yield LLMStreamChunk(finish_reason="stop")
                except json.JSONDecodeError:
                    continue
