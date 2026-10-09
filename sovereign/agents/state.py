"""Agent state — the typed state shared by all agents in the graph.

This is the LangGraph state schema. Every agent reads from and writes to
this state. The supervisor routes based on it; sub-agents update it.

Design:
- ``messages``: conversation history (for multi-turn)
- ``task_type``: classified by the supervisor
- ``query``: the user's original request
- ``project_id``: for isolation
- ``rag_response``: output of the RAG agent
- ``evidence_report``: output of the evidence verification agent
- ``findings``: output of the risk agent
- ``deliverable``: output of the deliverable agent
- ``audit_events``: collected for the audit trail
- ``errors``: non-fatal errors collected during execution
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

TaskType = Literal[
    "question",         # factual Q&A → RAG agent
    "document_analysis", # parse/analyze a document → DocIntel
    "image_analysis",    # understand an image → Vision
    "research",          # external research → Research (egress-gated)
    "risk_assessment",   # findings + risk → Risk agent
    "report_generation", # generate a deliverable → Deliverable agent
    "multi_step",        # complex task requiring multiple agents
]


class AgentState(TypedDict, total=False):
    """LangGraph state shared by all agents.

    ``total=False`` because not all fields are populated at every step.
    The supervisor populates ``task_type``; each sub-agent populates its
    own output field.
    """

    # Input
    query: str
    project_id: str
    document_id: str  # optional: for document-specific tasks

    # Supervisor output
    task_type: TaskType
    # Ordered list of agents to execute (for multi-step)
    agent_sequence: list[str]
    # Current agent index in the sequence
    current_step: int

    # Sub-agent outputs
    rag_response: dict[str, Any]  # RAGResponse.model_dump()
    evidence_report: dict[str, Any]  # EvidenceReport.model_dump()
    document_analysis: dict[str, Any]  # DocIntel output
    vision_description: str  # Vision output
    research_results: list[dict[str, Any]]  # Research output
    findings: list[dict[str, Any]]  # Risk output
    deliverable: dict[str, Any]  # Deliverable output

    # Metadata
    errors: list[str]
    audit_events: list[dict[str, Any]]
    steps_completed: list[str]


class AgentResponse(BaseModel):
    """API response for an agent orchestration request."""

    query: str
    task_type: str
    steps_completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Outputs (populated based on task type)
    rag_response: dict[str, Any] | None = None
    evidence_report: dict[str, Any] | None = None
    document_analysis: dict[str, Any] | None = None
    vision_description: str | None = None
    research_results: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    deliverable: dict[str, Any] | None = None

    @property
    def succeeded(self) -> bool:
        """True if no errors occurred."""
        return len(self.errors) == 0
