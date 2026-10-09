"""Agent orchestration API routes.

- POST /agents/query  — run the agent graph for a user request
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from sovereign.agents.state import AgentResponse
from sovereign.orchestration import get_orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])

_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    document_id: str | None = None  # optional: for document-specific tasks


class AgentQueryResponse(BaseModel):
    query: str
    task_type: str
    steps_completed: list[str]
    errors: list[str]
    succeeded: bool
    rag_response: dict[str, Any] | None = None
    evidence_report: dict[str, Any] | None = None
    document_analysis: dict[str, Any] | None = None
    vision_description: str | None = None
    research_results: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    deliverable: dict[str, Any] | None = None


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(req: AgentQueryRequest) -> AgentQueryResponse:
    """Run the agent graph for a user request.

    The supervisor classifies the request and routes to the appropriate
    sub-agent(s). Responses include outputs from all agents that ran.
    """
    orchestrator = get_orchestrator()
    response: AgentResponse = await orchestrator.run(
        project_id=_DEV_PROJECT_ID,
        query=req.query,
        document_id=req.document_id or "",
    )

    return AgentQueryResponse(
        query=response.query,
        task_type=response.task_type,
        steps_completed=response.steps_completed,
        errors=response.errors,
        succeeded=response.succeeded,
        rag_response=response.rag_response,
        evidence_report=response.evidence_report,
        document_analysis=response.document_analysis,
        vision_description=response.vision_description,
        research_results=response.research_results,
        findings=response.findings,
        deliverable=response.deliverable,
    )
