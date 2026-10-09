"""Supervisor agent — intent classification + task routing.

The supervisor is the entry point of the agent graph. It:
1. Classifies the user's request into a ``TaskType``.
2. Determines which sub-agent(s) should handle it.
3. Sets the ``agent_sequence`` for multi-step tasks.

In dev (MockBackend), classification uses keyword heuristics.
In prod, the LLM does real intent classification.
"""

from __future__ import annotations

import json

from sovereign.agents.state import AgentState, TaskType
from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway
from sovereign.models.schemas import LLMRequest, Message

log = get_logger(__name__)

_SYSTEM_PROMPT = """You are a task routing system for an industrial AI workbench.
Classify the user's request into one of these task types:
- "question": factual Q&A about documents in the knowledge base
- "document_analysis": parse, analyze, or extract from a document
- "image_analysis": understand or describe an image/diagram
- "research": external research (requires egress permission)
- "risk_assessment": analyze risks, findings, or safety concerns
- "report_generation": generate a report, summary, or deliverable
- "multi_step": complex task requiring multiple steps

Return a JSON object:
{"task_type": "...", "agent_sequence": ["agent1", "agent2", ...]}

Available agents: rag, doc_intel, vision, research, evidence_verify, risk, deliverable
Return ONLY valid JSON."""


class Supervisor:
    """Classifies user intent and routes to sub-agents.

    Usage::

        supervisor = Supervisor(gateway)
        state = supervisor.route(state)
        # state now has task_type and agent_sequence
    """

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            from sovereign.models.gateway import get_model_gateway

            self._gateway = get_model_gateway()
        return self._gateway

    async def classify(self, state: AgentState) -> AgentState:
        """Classify the request and set task_type + agent_sequence.

        Tries LLM classification first; falls back to heuristics.
        """
        query = state.get("query", "")

        # Try LLM classification
        try:
            resp = await self.gateway.text.complete(
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
            task_type = parsed.get("task_type", "question")
            agent_sequence = parsed.get("agent_sequence", ["rag"])

            # Validate task_type
            valid_types = {"question", "document_analysis", "image_analysis",
                          "research", "risk_assessment", "report_generation", "multi_step"}
            if task_type not in valid_types:
                task_type = "question"

            # Validate agent names
            valid_agents = {"rag", "doc_intel", "vision", "research",
                           "evidence_verify", "risk", "deliverable"}
            agent_sequence = [a for a in agent_sequence if a in valid_agents]
            if not agent_sequence:
                agent_sequence = self._default_sequence(task_type)

        except (json.JSONDecodeError, KeyError, TypeError):
            log.debug("supervisor.fallback_to_heuristic", query=query)
            task_type = self._heuristic_classify(query)
            agent_sequence = self._default_sequence(task_type)

        log.info(
            "supervisor.classified",
            task_type=task_type,
            agent_sequence=agent_sequence,
        )

        state["task_type"] = task_type
        state["agent_sequence"] = agent_sequence
        state["current_step"] = 0
        return state

    def _heuristic_classify(self, query: str) -> TaskType:
        """Simple keyword-based classification."""
        q = query.lower()

        if any(w in q for w in ("analyze", "parse", "extract", "summarize document")):
            return "document_analysis"
        if any(w in q for w in ("image", "diagram", "photo", "picture", "drawing")):
            return "image_analysis"
        if any(w in q for w in ("research", "external", "look up online")):
            return "research"
        if any(w in q for w in ("risk", "finding", "severity", "safety", "hazard")):
            return "risk_assessment"
        if any(w in q for w in ("report", "generate", "deliverable", "create document")):
            return "report_generation"
        if any(w in q for w in ("and then", "step by step", "first", "after that")):
            return "multi_step"
        return "question"

    def _default_sequence(self, task_type: TaskType) -> list[str]:
        """Return the default agent sequence for a task type."""
        sequences: dict[str, list[str]] = {
            "question": ["rag", "evidence_verify"],
            "document_analysis": ["doc_intel"],
            "image_analysis": ["vision"],
            "research": ["research"],
            "risk_assessment": ["rag", "evidence_verify", "risk"],
            "report_generation": ["rag", "evidence_verify", "deliverable"],
            "multi_step": ["rag", "evidence_verify"],
        }
        return sequences.get(task_type, ["rag"])
