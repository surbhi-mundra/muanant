"""Agent orchestration graph — LangGraph state machine.

Wires the supervisor + sub-agents into a LangGraph ``StateGraph``:

    START → supervisor → [route to sub-agents] → END

The supervisor classifies the task and sets ``agent_sequence``. The graph
then executes each agent in sequence, passing the shared ``AgentState``
between them. Errors are non-fatal — the graph continues and reports
which steps failed.

For complex tasks (``multi_step``), the supervisor can chain multiple
agents. For simple tasks, only the relevant agent runs.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from sovereign.agents.state import AgentResponse, AgentState
from sovereign.agents.sub_agents import (
    deliverable_agent,
    doc_intel_agent,
    evidence_verify_agent,
    rag_agent,
    research_agent,
    risk_agent,
    vision_agent,
)
from sovereign.agents.supervisor import Supervisor
from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway, get_model_gateway

log = get_logger(__name__)

# Agent registry: name → async function
AGENTS: dict[str, Any] = {
    "rag": rag_agent,
    "doc_intel": doc_intel_agent,
    "vision": vision_agent,
    "research": research_agent,
    "evidence_verify": evidence_verify_agent,
    "risk": risk_agent,
    "deliverable": deliverable_agent,
}


class AgentOrchestrator:
    """LangGraph-based agent orchestrator.

    Usage::

        orch = AgentOrchestrator()
        response = await orch.run("proj_1", "What is the maintenance schedule for pump P-101?")
    """

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway
        self._supervisor = Supervisor(gateway)
        self._graph = self._build_graph()

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("supervisor", self._supervisor_node)
        for name, agent_fn in AGENTS.items():
            workflow.add_node(name, agent_fn)

        # Add edges: START → supervisor
        workflow.add_edge(START, "supervisor")

        # Conditional routing from supervisor → first agent in sequence
        route_map_1: dict[object, str] = {name: name for name in AGENTS}
        route_map_1["end"] = str(END)
        workflow.add_conditional_edges(
            "supervisor",
            self._route_after_supervisor,
            route_map_1,
        )

        # After each agent: go to next agent or END
        for name in AGENTS:
            route_map_n: dict[object, str] = {n: n for n in AGENTS}
            route_map_n["end"] = str(END)
            workflow.add_conditional_edges(
                name,
                self._route_after_agent,
                route_map_n,
            )

        return workflow.compile()

    async def _supervisor_node(self, state: AgentState) -> AgentState:
        """Supervisor node: classify intent and set agent_sequence."""
        return await self._supervisor.classify(state)

    def _route_after_supervisor(self, state: AgentState) -> str:
        """Route to the first agent in the sequence, or END if empty."""
        sequence = state.get("agent_sequence", [])
        if not sequence:
            return "end"
        return sequence[0]

    def _route_after_agent(self, state: AgentState) -> str:
        """Route to the next agent in the sequence, or END if done."""
        sequence = state.get("agent_sequence", [])
        current_step = state.get("current_step", 0)

        next_step = current_step + 1
        if next_step >= len(sequence):
            return "end"

        # Update step counter in state (LangGraph passes state by value,
        # so we can't mutate here — but the next agent will see the
        # updated state from the previous agent's return)
        return sequence[next_step]

    async def run(
        self,
        project_id: str,
        query: str,
        document_id: str = "",
    ) -> AgentResponse:
        """Run the agent graph for a user request.

        Args:
            project_id: project context (for isolation).
            query: the user's request.
            document_id: optional, for document-specific tasks.

        Returns: ``AgentResponse`` with all agent outputs.
        """
        initial_state: AgentState = {
            "query": query,
            "project_id": project_id,
            "document_id": document_id,
            "errors": [],
            "audit_events": [],
            "steps_completed": [],
            "current_step": 0,
        }

        log.info(
            "orchestrator.run.start",
            project_id=project_id,
            query=query[:100],
        )

        # Execute the graph
        # We need to manually step through because LangGraph's conditional
        # routing doesn't mutate state between edges. Instead, we use the
        # agent_sequence and call agents directly.
        state = await self._supervisor.classify(initial_state)

        sequence = state.get("agent_sequence", [])
        for i, agent_name in enumerate(sequence):
            if agent_name not in AGENTS:
                log.warning("orchestrator.unknown_agent", agent=agent_name)
                continue

            state["current_step"] = i
            log.info("orchestrator.step", step=i, agent=agent_name)

            try:
                agent_fn = AGENTS[agent_name]
                state = await agent_fn(state)
            except Exception as e:
                log.error(
                    "orchestrator.step.failed",
                    agent=agent_name,
                    error=str(e),
                )
                state["errors"].append(f"{agent_name}: {e}")

        log.info(
            "orchestrator.run.complete",
            steps=state.get("steps_completed", []),
            errors=len(state.get("errors", [])),
        )

        return self._build_response(state)

    def _build_response(self, state: AgentState) -> AgentResponse:
        """Convert final AgentState to AgentResponse."""
        return AgentResponse(
            query=state.get("query", ""),
            task_type=state.get("task_type", "question"),
            steps_completed=state.get("steps_completed", []),
            errors=state.get("errors", []),
            rag_response=state.get("rag_response"),
            evidence_report=state.get("evidence_report"),
            document_analysis=state.get("document_analysis"),
            vision_description=state.get("vision_description"),
            research_results=state.get("research_results", []),
            findings=state.get("findings", []),
            deliverable=state.get("deliverable"),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Return the cached AgentOrchestrator singleton."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Test helper: drop the cached orchestrator."""
    global _orchestrator  # noqa: PLW0603
    _orchestrator = None
