"""Stage 1 — Query understanding.

Classifies the query intent and extracts constraints. Uses the LLM (via
ModelGateway's TextLLM) with a structured prompt.

In dev (MockBackend), this returns a simple heuristic classification.
In prod, the LLM does real intent classification.
"""

from __future__ import annotations

import json

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway
from sovereign.models.schemas import LLMRequest, Message
from sovereign.rag.model import QueryAnalysis, QueryIntent

log = get_logger(__name__)

_SYSTEM_PROMPT = """You are a query understanding system for an industrial knowledge base.
Analyze the user's query and return a JSON object with:
- "intent": one of "factual", "procedural", "analytical", "comparative",
  "definitional", "conversational"
- "key_terms": list of important terms for keyword search
- "constraints": dict of extracted constraints (e.g. {"equipment": "P-101"})
- "needs_external": true if the query likely needs external research
- "rewritten_queries": 1-3 reformulated versions for better retrieval

Return ONLY valid JSON, no explanation."""


async def understand_query(
    query: str, gateway: ModelGateway
) -> QueryAnalysis:
    """Stage 1: understand the query.

    Calls the LLM with a structured prompt. Falls back to a simple
    heuristic if the LLM returns invalid JSON.
    """
    try:
        resp = await gateway.text.complete(
            LLMRequest(
                messages=[
                    Message(role="system", content=_SYSTEM_PROMPT),
                    Message(role="user", content=query),
                ],
                json_mode=True,
                temperature=0.0,
            )
        )

        parsed = json.loads(resp.content)
        return QueryAnalysis(
            intent=parsed.get("intent", "factual"),
            key_terms=parsed.get("key_terms", []),
            constraints=parsed.get("constraints", {}),
            needs_external=parsed.get("needs_external", False),
            rewritten_queries=parsed.get("rewritten_queries", []),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.debug("rag.understand.fallback", query=query, error=str(e))
        return _heuristic_understand(query)


def _heuristic_understand(query: str) -> QueryAnalysis:
    """Simple rule-based query understanding (fallback / mock mode)."""
    q_lower = query.lower()

    # Intent classification by keyword
    intent: QueryIntent = "factual"
    if any(w in q_lower for w in ("how", "steps", "procedure", "process")):
        intent = "procedural"
    elif any(w in q_lower for w in ("compare", "versus", "vs", "difference")):
        intent = "comparative"
    elif any(w in q_lower for w in ("what is", "define", "definition", "meaning")):
        intent = "definitional"
    elif any(w in q_lower for w in ("analyze", "why", "impact", "cause", "effect")):
        intent = "analytical"

    # Extract key terms (simple: words > 3 chars, no stopwords)
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why",
                 "for", "of", "to", "in", "on", "at", "by", "with", "from"}
    words = [w.strip(".,!?;:()[]").lower() for w in query.split()]
    key_terms = [w for w in words if len(w) > 2 and w not in stopwords]

    return QueryAnalysis(
        intent=intent,
        key_terms=key_terms,
        constraints={},
        needs_external=False,
        rewritten_queries=[],  # mock doesn't rewrite
    )
