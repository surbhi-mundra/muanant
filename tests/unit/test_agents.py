"""Tests for sovereign.agents — supervisor, sub-agents, orchestrator."""

from __future__ import annotations

import pytest

from sovereign.agents.state import AgentResponse, AgentState
from sovereign.agents.sub_agents import (
    deliverable_agent,
    doc_intel_agent,
    evidence_verify_agent,
    rag_agent,
    research_agent,
    risk_agent,
)
from sovereign.agents.supervisor import Supervisor
from sovereign.embeddings.indexing import reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.orchestration import AgentOrchestrator, reset_orchestrator
from sovereign.parsing.model import Block, DocumentMetadata, Page, ParsedDocument
from sovereign.rag.pipeline import reset_rag_pipeline
from sovereign.storage.qdrant import reset_qdrant_store


@pytest.fixture(autouse=True)
def _reset_all():
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()
    reset_orchestrator()
    yield
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()
    reset_orchestrator()


def _make_state(**kwargs) -> AgentState:
    """Build a minimal AgentState for testing."""
    base: AgentState = {
        "query": kwargs.get("query", "test query"),
        "project_id": kwargs.get("project_id", "proj_test"),
        "document_id": kwargs.get("document_id", ""),
        "errors": [],
        "audit_events": [],
        "steps_completed": [],
        "current_step": 0,
    }
    base.update(kwargs)  # type: ignore[typeddict-assignment]
    return base


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------
class TestSupervisor:
    async def test_classify_question(self) -> None:
        """Should classify a factual query as 'question'."""
        sup = Supervisor()
        state = await sup.classify(_make_state(query="What is the pressure rating of pump P-101?"))
        assert state["task_type"] in ("question", "factual")
        assert "rag" in state["agent_sequence"]

    async def test_classify_document_analysis(self) -> None:
        """Should classify document analysis requests."""
        sup = Supervisor()
        state = await sup.classify(
            _make_state(query="Analyze this document and extract key information.")
        )
        assert state["task_type"] in ("document_analysis", "question")
        assert len(state["agent_sequence"]) > 0

    async def test_classify_image_analysis(self) -> None:
        """Should classify image analysis requests."""
        sup = Supervisor()
        state = await sup.classify(_make_state(query="Describe what's in this image."))
        assert state["task_type"] in ("image_analysis", "question")
        assert len(state["agent_sequence"]) > 0

    async def test_classify_risk_assessment(self) -> None:
        """Should classify risk assessment requests."""
        sup = Supervisor()
        state = await sup.classify(_make_state(query="What are the safety risks and hazards?"))
        assert state["task_type"] in ("risk_assessment", "question")
        assert len(state["agent_sequence"]) > 0

    async def test_classify_report_generation(self) -> None:
        """Should classify report generation requests."""
        sup = Supervisor()
        state = await sup.classify(_make_state(query="Generate a report on the findings."))
        assert state["task_type"] in ("report_generation", "question")
        assert len(state["agent_sequence"]) > 0

    def test_heuristic_classify_keywords(self) -> None:
        """Heuristic classifier should detect keywords."""
        sup = Supervisor()
        assert sup._heuristic_classify("analyze the document") == "document_analysis"
        assert sup._heuristic_classify("look at this image") == "image_analysis"
        assert sup._heuristic_classify("research this externally") == "research"
        assert sup._heuristic_classify("what are the risks") == "risk_assessment"
        assert sup._heuristic_classify("generate a report") == "report_generation"
        assert sup._heuristic_classify("what is pump P-101") == "question"

    def test_default_sequence(self) -> None:
        """Each task type should have a default agent sequence."""
        sup = Supervisor()
        assert sup._default_sequence("question") == ["rag", "evidence_verify"]
        assert sup._default_sequence("document_analysis") == ["doc_intel"]
        assert sup._default_sequence("image_analysis") == ["vision"]
        assert sup._default_sequence("research") == ["research"]
        assert "risk" in sup._default_sequence("risk_assessment")
        assert "deliverable" in sup._default_sequence("report_generation")

    async def test_classify_sets_current_step(self) -> None:
        """After classification, current_step should be 0."""
        sup = Supervisor()
        state = await sup.classify(_make_state(query="test"))
        assert state["current_step"] == 0


# ---------------------------------------------------------------------------
# Sub-agents
# ---------------------------------------------------------------------------
class TestSubAgents:
    async def test_rag_agent_runs(self) -> None:
        """RAG agent should execute and populate rag_response."""
        state = _make_state(query="test question", project_id="proj_empty")
        result = await rag_agent(state)
        assert "rag" in result["steps_completed"]
        assert "rag_response" in result or len(result["errors"]) > 0

    async def test_rag_agent_populates_rag_response(self) -> None:
        """RAG agent should populate rag_response when it succeeds."""
        # Index a document first
        from sovereign.embeddings.indexing import IndexingService

        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="test.txt", source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[
                Block(kind="paragraph", text="Pump P-101 requires maintenance every 6 months."),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        state = _make_state(
            query="How often does pump P-101 need maintenance?",
            project_id="proj_test",
        )
        result = await rag_agent(state)
        assert "rag_response" in result
        assert result["rag_response"] is not None

    async def test_research_agent_blocked_by_default(self) -> None:
        """Research agent should be blocked when egress is off (default)."""
        state = _make_state(query="research this topic")
        result = await research_agent(state)
        assert "research" in result["steps_completed"]
        assert len(result["research_results"]) > 0
        assert result["research_results"][0]["source"] == "blocked"

    async def test_evidence_verify_agent(self) -> None:
        """Evidence verify agent should add verification summary."""
        state = _make_state(
            query="test",
            rag_response={"claims": [{"text": "test claim", "support_status": "SUPPORTED"}]},
            evidence_report={"citations": [], "contradictions": []},
        )
        result = await evidence_verify_agent(state)
        assert "evidence_verify" in result["steps_completed"]
        report = result.get("evidence_report", {})
        assert "verification_summary" in report

    async def test_evidence_verify_skips_without_rag(self) -> None:
        """Evidence verify should skip if no rag_response."""
        state = _make_state(query="test")
        result = await evidence_verify_agent(state)
        # Should not crash, just skip
        assert "evidence_verify" in result["steps_completed"]

    async def test_risk_agent_extracts_findings(self) -> None:
        """Risk agent should find risk-related keywords."""
        state = _make_state(
            query="test",
            rag_response={
                "answer": "There is a critical failure risk with the pump bearing.",
                "evidence": [{"text": "bearing wear detected", "document_id": "doc1"}],
            },
        )
        result = await risk_agent(state)
        assert "risk" in result["steps_completed"]
        findings = result.get("findings", [])
        # Should find "risk", "failure", "wear" at minimum
        assert len(findings) > 0
        # At least one should be CRITICAL (from "failure")
        severities = [f["severity"] for f in findings]
        assert "CRITICAL" in severities

    async def test_risk_agent_no_findings_when_safe(self) -> None:
        """Risk agent should find nothing when content is safe."""
        state = _make_state(
            query="test",
            rag_response={
                "answer": "The pump is operating normally within parameters.",
                "evidence": [],
            },
        )
        result = await risk_agent(state)
        findings = result.get("findings", [])
        assert len(findings) == 0

    async def test_deliverable_agent_builds_report(self) -> None:
        """Deliverable agent should combine outputs into a report."""
        state = _make_state(
            query="What is the maintenance schedule?",
            rag_response={"answer": "Maintenance every 6 months.", "evidence": []},
            findings=[{"description": "bearing wear", "severity": "HIGH"}],
            evidence_report={
                "citations": [
                    {"source_label": "doc1.txt", "support_status": "SUPPORTED"}
                ]
            },
        )
        result = await deliverable_agent(state)
        assert "deliverable" in result
        deliverable = result["deliverable"]
        assert "sections" in deliverable
        assert len(deliverable["sections"]) >= 1

    async def test_deliverable_includes_findings(self) -> None:
        """Deliverable should include findings section when findings exist."""
        state = _make_state(
            query="test",
            rag_response={"answer": "test", "evidence": []},
            findings=[{"description": "risk found", "severity": "HIGH"}],
            evidence_report={},
        )
        result = await deliverable_agent(state)
        sections = result["deliverable"]["sections"]
        headings = [s["heading"] for s in sections]
        assert "Findings" in headings

    async def test_agent_errors_are_non_fatal(self) -> None:
        """Agent errors should be caught and added to errors list, not raised."""
        state = _make_state(query="test", project_id="nonexistent_project")
        state["document_id"] = "nonexistent_doc"
        result = await doc_intel_agent(state)
        # Should have an error but not crash
        assert len(result["errors"]) > 0
        assert "doc_intel" in result["steps_completed"]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class TestOrchestrator:
    async def test_run_question_task(self) -> None:
        """Running a question should route through RAG + evidence_verify."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_test", "What is pump P-101?")

        assert isinstance(response, AgentResponse)
        assert response.task_type in ("question", "factual")
        assert len(response.steps_completed) > 0

    async def test_run_returns_response_type(self) -> None:
        """run() should return an AgentResponse."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_test", "test query")
        assert isinstance(response, AgentResponse)
        assert response.query == "test query"

    async def test_run_includes_steps_completed(self) -> None:
        """Response should include which agents ran."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_test", "What is the maintenance schedule?")
        assert len(response.steps_completed) > 0
        # Supervisor always runs first (implicitly), then agents
        assert any(
            step in response.steps_completed
            for step in ["rag", "evidence_verify", "supervisor"]
        )

    async def test_run_empty_kb(self) -> None:
        """Running on an empty KB should not crash."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_empty", "What is pump P-101?")
        assert response.succeeded or len(response.errors) > 0  # either is fine

    async def test_run_with_document_id(self) -> None:
        """Running with a document_id should route to doc_intel."""
        orch = AgentOrchestrator()
        response = await orch.run(
            "proj_test",
            "Analyze this document",
            document_id="some_doc_id",
        )
        assert isinstance(response, AgentResponse)
        # May error because doc doesn't exist, but should not crash
        assert response.task_type in ("document_analysis", "question")

    async def test_run_research_blocked(self) -> None:
        """Research task should be blocked by default (egress off)."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_test", "research this topic externally")
        if response.research_results:
            assert response.research_results[0]["source"] in ("blocked", "placeholder")

    async def test_run_risk_assessment(self) -> None:
        """Risk assessment should route through rag + risk agents."""
        orch = AgentOrchestrator()
        response = await orch.run("proj_test", "What are the safety risks?")
        assert isinstance(response, AgentResponse)
        # Risk agent should have run if task was classified as risk_assessment
        if response.task_type == "risk_assessment":
            assert "risk" in response.steps_completed or len(response.errors) > 0
