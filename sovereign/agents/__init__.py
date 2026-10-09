"""Agent orchestration — LangGraph supervisor + sub-agents.

This package implements the supervisor-based agent architecture:

- ``Supervisor``: classifies intent, decomposes tasks, routes to sub-agents
- ``DocIntelAgent``: document parsing, OCR, classification, table extraction
- ``VisionAgent``: image understanding, diagrams, inspection images
- ``RAGAgent``: retrieval, evidence selection, grounded reasoning
- ``ResearchAgent``: external research (egress-gated, no KB access)
- ``EvidenceVerifyAgent``: verifies claims, detects contradictions
- ``RiskAgent``: findings, severity, recommended actions
- ``DeliverableAgent``: reports, summaries, action lists

All agents share a typed ``AgentState`` and communicate via the LangGraph
state graph. The supervisor routes work; sub-agents execute and return
updated state.
"""

from sovereign.agents.state import AgentResponse, AgentState, TaskType
from sovereign.agents.supervisor import Supervisor

__all__ = [
    "AgentResponse",
    "AgentState",
    "Supervisor",
    "TaskType",
]
