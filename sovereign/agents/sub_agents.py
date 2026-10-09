"""Sub-agents — each handles a specific capability.

All sub-agents follow the same contract:
- Take ``AgentState`` as input.
- Execute their capability.
- Return updated ``AgentState`` with their output field populated.
- Catch errors and append to ``state["errors"]`` (non-fatal).

The supervisor routes to these; they never call each other directly.
"""

from __future__ import annotations

from typing import Any

from sovereign.agents.state import AgentState
from sovereign.core.logging import get_logger

log = get_logger(__name__)


def _safe_execute(agent_name: str, state: AgentState) -> AgentState:
    """Decorator-like wrapper: ensure errors are caught, not raised.

    If a sub-agent raises, we log the error and add it to state["errors"]
    so the graph continues (non-fatal). The deliverable agent can report
    which steps failed.
    """
    state.setdefault("errors", [])
    state.setdefault("steps_completed", [])
    state["steps_completed"].append(agent_name)
    return state


# ---------------------------------------------------------------------------
# RAG Agent
# ---------------------------------------------------------------------------
async def rag_agent(state: AgentState) -> AgentState:
    """Knowledge/RAG agent — grounded retrieval + reasoning.

    Uses the 9-stage RAG pipeline (Phase 5) to answer the query.
    """
    from sovereign.rag.pipeline import get_rag_pipeline

    log.info("agent.rag.start", query=state.get("query", "")[:100])
    state = _safe_execute("rag", state)

    try:
        project_id = state.get("project_id", "")
        query = state.get("query", "")
        document_id = state.get("document_id")
        document_filter = {"document_id": document_id} if document_id else None

        pipeline = get_rag_pipeline()
        response = await pipeline.query(
            project_id=project_id,
            query=query,
            document_filter=document_filter,
        )

        state["rag_response"] = response.model_dump()
        if response.evidence_report is not None:
            # evidence_report is typed as object|None in RAGResponse to avoid
            # circular imports; here we know it's an EvidenceReport.
            from sovereign.evidence.model import EvidenceReport

            report: EvidenceReport = response.evidence_report  # type: ignore[assignment]
            state["evidence_report"] = report.model_dump()

        log.info(
            "agent.rag.complete",
            verdict=response.verdict.kind,
            evidence_count=len(response.evidence),
        )
    except Exception as e:
        log.error("agent.rag.failed", error=str(e))
        state["errors"].append(f"rag: {e}")

    return state


# ---------------------------------------------------------------------------
# Document Intelligence Agent
# ---------------------------------------------------------------------------
async def doc_intel_agent(state: AgentState) -> AgentState:
    """Document Intelligence agent — parsing, metadata, summarization.

    Retrieves the parsed document and provides a summary + metadata.
    """
    from sovereign.ingestion.service import get_document, get_parsed_document

    log.info("agent.doc_intel.start", document_id=state.get("document_id"))
    state = _safe_execute("doc_intel", state)

    try:
        project_id = state.get("project_id", "")
        document_id = state.get("document_id", "")

        if not document_id:
            state["errors"].append("doc_intel: no document_id specified")
            return state

        doc = get_document(project_id, document_id)
        parsed = get_parsed_document(project_id, document_id)

        state["document_analysis"] = {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "page_count": parsed.metadata.page_count,
            "word_count": parsed.metadata.word_count,
            "heading_count": len(parsed.headings),
            "table_count": len(parsed.tables),
            "figure_count": len(parsed.figures),
            "metadata": parsed.metadata.model_dump(),
            "total_text_preview": parsed.total_text[:500],
        }

        log.info(
            "agent.doc_intel.complete",
            document_id=document_id,
            pages=parsed.metadata.page_count,
            tables=len(parsed.tables),
        )
    except Exception as e:
        log.error("agent.doc_intel.failed", error=str(e))
        state["errors"].append(f"doc_intel: {e}")

    return state


# ---------------------------------------------------------------------------
# Vision Agent
# ---------------------------------------------------------------------------
async def vision_agent(state: AgentState) -> AgentState:
    """Vision agent — image/diagram understanding via VisionLLM.

    If a document_id is provided, describes its first figure.
    Otherwise, describes the query as if it were an image prompt.
    """
    from sovereign.vision.service import VisionService

    log.info("agent.vision.start")
    state = _safe_execute("vision", state)

    try:
        query = state.get("query", "")
        document_id = state.get("document_id", "")

        if document_id:
            from sovereign.ingestion.service import get_document
            from sovereign.storage.objects import get_object_store

            project_id = state.get("project_id", "")
            doc = get_document(project_id, document_id)
            store = get_object_store()
            image_data = store.get(project_id, doc.storage_key)

            service = VisionService()
            if doc.mime_type.startswith("image/"):
                result = await service.describe_inspection_image(image_data, doc.mime_type)
            else:
                result = await service.describe_diagram(image_data, "image/png")
            state["vision_description"] = result.text
        else:
            # No image — use the query as a prompt with a placeholder
            state["vision_description"] = (
                f"[vision agent] No image provided. Query was: {query}"
            )

        log.info("agent.vision.complete", desc_len=len(state.get("vision_description", "")))
    except Exception as e:
        log.error("agent.vision.failed", error=str(e))
        state["errors"].append(f"vision: {e}")

    return state


# ---------------------------------------------------------------------------
# Research Agent (egress-gated)
# ---------------------------------------------------------------------------
async def research_agent(state: AgentState) -> AgentState:
    """Research agent — external research with egress control.

    CRITICAL: This agent has NO access to the knowledge base. It can only
    make external HTTP requests via the egress gateway (off by default).
    It never sees confidential document content.

    In dev/CI, egress is disabled, so this agent returns a placeholder.
    """
    from sovereign.core.config import get_settings

    log.info("agent.research.start")
    state = _safe_execute("research", state)

    settings = get_settings()
    if not settings.egress_enabled:
        state["research_results"] = [{
            "source": "blocked",
            "message": "External research is disabled (egress off by default). "
                       "Enable via EGRESS_ENABLED=true + policies.yaml allowlist.",
        }]
        log.info("agent.research.blocked", reason="egress_disabled")
        return state

    # Egress is enabled — but we still don't have a real egress gateway yet
    # (Phase 11). For now, return a placeholder.
    state["research_results"] = [{
        "source": "placeholder",
        "message": "Egress gateway not yet implemented (Phase 11). "
                   "External research will be available after Phase 11.",
    }]
    log.info("agent.research.placeholder")

    return state


# ---------------------------------------------------------------------------
# Evidence Verification Agent
# ---------------------------------------------------------------------------
async def evidence_verify_agent(state: AgentState) -> AgentState:
    """Evidence verification agent — verifies claims + detects contradictions.

    If the RAG agent ran, takes its response and verifies the claims.
    If an evidence_report was already built, adds contradiction detection.
    """
    log.info("agent.evidence_verify.start")
    state = _safe_execute("evidence_verify", state)

    try:
        rag_response = state.get("rag_response")

        if not rag_response:
            log.info("agent.evidence_verify.skip", reason="no rag_response")
            return state

        # The RAG pipeline already does evidence verification (stage 8).
        # This agent can add additional cross-checking here in the future.
        # For now, it confirms the verification status.
        claims = rag_response.get("claims", [])
        supported = sum(1 for c in claims if c.get("support_status") == "SUPPORTED")

        evidence_report = state.get("evidence_report", {})
        contradictions = evidence_report.get("contradictions", [])

        state["evidence_report"] = {
            **evidence_report,
            "verification_summary": {
                "total_claims": len(claims),
                "supported_claims": supported,
                "contradictions_found": len(contradictions),
            },
        }

        log.info(
            "agent.evidence_verify.complete",
            claims=len(claims),
            supported=supported,
            contradictions=len(contradictions),
        )
    except Exception as e:
        log.error("agent.evidence_verify.failed", error=str(e))
        state["errors"].append(f"evidence_verify: {e}")

    return state


# ---------------------------------------------------------------------------
# Risk Agent
# ---------------------------------------------------------------------------
async def risk_agent(state: AgentState) -> AgentState:
    """Risk/Decision agent — findings, severity, recommended actions.

    Analyzes the RAG response + evidence for risk-related content.
    Extracts findings and assigns severity.
    """
    log.info("agent.risk.start")
    state = _safe_execute("risk", state)

    try:
        rag_response = state.get("rag_response", {})
        answer = rag_response.get("answer", "")
        evidence = rag_response.get("evidence", [])

        findings: list[dict[str, Any]] = []

        # Simple heuristic: look for risk-related keywords in the answer
        risk_keywords = ["risk", "hazard", "danger", "warning", "critical",
                        "failure", "leak", "corrosion", "wear", "damage"]

        answer_lower = answer.lower()
        for keyword in risk_keywords:
            if keyword in answer_lower:
                findings.append({
                    "description": f"Risk-related content detected: '{keyword}'",
                    "severity": _classify_severity(keyword),
                    "source": "answer",
                })

        # Also check evidence for risk content
        for ev in evidence:
            ev_text = ev.get("text", "").lower()
            for keyword in risk_keywords:
                if keyword in ev_text:
                    findings.append({
                        "description": f"Evidence contains: '{keyword}'",
                        "severity": _classify_severity(keyword),
                        "source": ev.get("document_id", "unknown"),
                    })

        state["findings"] = findings

        log.info("agent.risk.complete", findings=len(findings))
    except Exception as e:
        log.error("agent.risk.failed", error=str(e))
        state["errors"].append(f"risk: {e}")

    return state


def _classify_severity(keyword: str) -> str:
    """Classify severity based on keyword."""
    critical = {"failure", "critical", "danger", "leak"}
    high = {"hazard", "warning", "damage"}
    medium = {"risk", "corrosion", "wear"}
    if keyword in critical:
        return "CRITICAL"
    if keyword in high:
        return "HIGH"
    if keyword in medium:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Deliverable Agent
# ---------------------------------------------------------------------------
async def deliverable_agent(state: AgentState) -> AgentState:
    """Deliverable agent — generates reports, summaries, action lists.

    Combines outputs from prior agents into a structured deliverable.
    """
    log.info("agent.deliverable.start")
    state = _safe_execute("deliverable", state)

    try:
        query = state.get("query", "")
        rag_response = state.get("rag_response", {})
        findings = state.get("findings", [])
        evidence_report = state.get("evidence_report", {})

        # Build a simple deliverable structure
        deliverable: dict[str, Any] = {
            "type": "summary",
            "title": f"Response to: {query[:100]}",
            "sections": [],
        }

        # Answer section
        answer = rag_response.get("answer", "")
        if answer:
            deliverable["sections"].append({
                "heading": "Answer",
                "content": answer,
            })

        # Findings section
        if findings:
            deliverable["sections"].append({
                "heading": "Findings",
                "items": [
                    {
                        "description": f["description"],
                        "severity": f["severity"],
                    }
                    for f in findings
                ],
            })

        # Evidence section
        citations = evidence_report.get("citations", [])
        if citations:
            deliverable["sections"].append({
                "heading": "Evidence",
                "items": [
                    {
                        "source": c.get("source_label", ""),
                        "status": c.get("support_status", ""),
                    }
                    for c in citations
                ],
            })

        # Steps completed
        deliverable["metadata"] = {
            "steps_completed": state.get("steps_completed", []),
            "errors": state.get("errors", []),
        }

        state["deliverable"] = deliverable

        log.info("agent.deliverable.complete", sections=len(deliverable["sections"]))
    except Exception as e:
        log.error("agent.deliverable.failed", error=str(e))
        state["errors"].append(f"deliverable: {e}")

    return state
