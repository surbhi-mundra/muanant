"""Deliverable builder — constructs deliverables from agent outputs.

Takes the outputs of the agent orchestration (RAG response, evidence,
findings, risk report) and builds a structured ``Deliverable``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sovereign.core.ids import new_ulid
from sovereign.deliverables.model import (
    Deliverable,
    DeliverableMetadata,
    DeliverableSection,
    DeliverableType,
)


class DeliverableBuilder:
    """Builds deliverables from agent outputs.

    Usage::

        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="inspection_report",
            query="What is the condition of pump P-101?",
            rag_response={...},
            findings=[...],
            evidence_report={...},
        )
    """

    def build(
        self,
        deliverable_type: DeliverableType,
        query: str,
        project_id: str = "",
        rag_response: dict[str, Any] | None = None,
        findings: list[dict[str, Any]] | None = None,
        evidence_report: dict[str, Any] | None = None,
        risk_report: dict[str, Any] | None = None,
        document_analysis: dict[str, Any] | None = None,
        vision_description: str | None = None,
    ) -> Deliverable:
        """Build a deliverable from agent outputs.

        Assembles sections based on the deliverable type and available
        agent outputs. Each type has a different template.
        """
        rag_response = rag_response or {}
        findings = findings or []
        evidence_report = evidence_report or {}
        risk_report = risk_report or {}
        document_analysis = document_analysis or {}

        # Build metadata
        metadata = DeliverableMetadata(
            title=self._build_title(deliverable_type, query),
            deliverable_type=deliverable_type,
            created_at=datetime.now(UTC).isoformat(),
            project_id=project_id,
            query=query,
        )

        sections: list[DeliverableSection] = []

        # 1. Executive Summary (always)
        sections.append(self._build_summary_section(
            deliverable_type, query, rag_response, findings, risk_report
        ))

        # 2. Answer / Findings
        if rag_response.get("answer"):
            sections.append(DeliverableSection(
                heading="Response",
                content=rag_response["answer"],
            ))

        # 3. Document Analysis (if available)
        if document_analysis:
            sections.append(self._build_document_section(document_analysis))

        # 4. Vision Description (if available)
        if vision_description:
            sections.append(DeliverableSection(
                heading="Visual Analysis",
                content=vision_description,
            ))

        # 5. Risk Assessment (if findings exist)
        if findings:
            sections.append(self._build_findings_section(findings))

        # 6. Risk Report (if available)
        if risk_report:
            sections.append(self._build_risk_section(risk_report))

        # 7. Evidence & Citations (if available)
        citations = evidence_report.get("citations", [])
        if citations:
            sections.append(self._build_evidence_section(evidence_report))

        # 8. Recommendations (from risk report)
        if risk_report.get("recommendations"):
            sections.append(DeliverableSection(
                heading="Recommendations",
                items=[{"action": r} for r in risk_report["recommendations"]],
            ))

        # 9. Action List (for action_list type)
        if deliverable_type == "action_list":
            sections.append(self._build_action_list(findings, risk_report))

        return Deliverable(
            metadata=metadata,
            sections=sections,
            citations=citations,
            findings=findings,
            metadata_extra={
                "deliverable_id": new_ulid(),
                "rag_verdict": rag_response.get("verdict", {}),
            },
        )

    def _build_title(self, deliverable_type: DeliverableType, query: str) -> str:
        """Build a title from the deliverable type and query."""
        type_labels = {
            "inspection_report": "Inspection Report",
            "maintenance_report": "Maintenance Report",
            "incident_report": "Incident Report",
            "executive_summary": "Executive Summary",
            "action_list": "Action List",
            "risk_assessment": "Risk Assessment",
            "summary": "Summary",
            "custom": "Report",
        }
        label = type_labels.get(deliverable_type, "Report")
        query_short = query[:80] + ("..." if len(query) > 80 else "")
        return f"{label}: {query_short}"

    def _build_summary_section(
        self,
        deliverable_type: DeliverableType,
        query: str,
        rag_response: dict[str, Any],
        findings: list[dict[str, Any]],
        risk_report: dict[str, Any],
    ) -> DeliverableSection:
        """Build the executive summary section."""
        parts: list[str] = []

        verdict = rag_response.get("verdict", {})
        if verdict.get("kind") == "answered":
            parts.append("This report provides a grounded answer to the query based on evidence from the knowledge base.")
        elif verdict.get("kind") == "insufficient_evidence":
            parts.append("WARNING: The knowledge base did not contain sufficient evidence to fully answer this query.")

        if findings:
            critical = [f for f in findings if f.get("severity") == "CRITICAL"]
            high = [f for f in findings if f.get("severity") == "HIGH"]
            if critical:
                parts.append(f"{len(critical)} critical finding(s) identified.")
            if high:
                parts.append(f"{len(high)} high-severity finding(s) identified.")

        if risk_report.get("overall_risk_score"):
            parts.append(
                f"Overall risk score: {risk_report['overall_risk_score']}/100 "
                f"({risk_report.get('risk_level', 'UNKNOWN')})."
            )

        content = " ".join(parts) if parts else "No summary available."

        return DeliverableSection(
            heading="Executive Summary",
            content=content,
        )

    def _build_document_section(self, doc_analysis: dict[str, Any]) -> DeliverableSection:
        """Build the document analysis section."""
        items = [
            {"label": "Filename", "value": doc_analysis.get("filename", "")},
            {"label": "MIME Type", "value": doc_analysis.get("mime_type", "")},
            {"label": "Pages", "value": str(doc_analysis.get("page_count", 0))},
            {"label": "Word Count", "value": str(doc_analysis.get("word_count", 0))},
            {"label": "Headings", "value": str(doc_analysis.get("heading_count", 0))},
            {"label": "Tables", "value": str(doc_analysis.get("table_count", 0))},
            {"label": "Figures", "value": str(doc_analysis.get("figure_count", 0))},
        ]
        return DeliverableSection(
            heading="Document Analysis",
            items=items,
        )

    def _build_findings_section(self, findings: list[dict[str, Any]]) -> DeliverableSection:
        """Build the findings section."""
        items = [
            {
                "description": f.get("description", ""),
                "severity": f.get("severity", "UNKNOWN"),
                "category": f.get("category", "general"),
                "recommended_actions": f.get("recommended_actions", []),
            }
            for f in findings
        ]
        return DeliverableSection(
            heading="Findings",
            items=items,
        )

    def _build_risk_section(self, risk_report: dict[str, Any]) -> DeliverableSection:
        """Build the risk assessment section."""
        return DeliverableSection(
            heading="Risk Assessment",
            content=risk_report.get("summary", ""),
            items=[
                {"label": "Risk Score", "value": str(risk_report.get("overall_risk_score", 0))},
                {"label": "Risk Level", "value": risk_report.get("risk_level", "UNKNOWN")},
                {"label": "Total Findings", "value": str(risk_report.get("total_findings", 0))},
            ],
        )

    def _build_evidence_section(self, evidence_report: dict[str, Any]) -> DeliverableSection:
        """Build the evidence & citations section."""
        citations = evidence_report.get("citations", [])
        contradictions = evidence_report.get("contradictions", [])
        items = [
            {
                "source": c.get("source_label", c.get("document_id", "")),
                "status": c.get("support_status", ""),
                "text": c.get("evidence_text", "")[:200],
            }
            for c in citations
        ]
        content = ""
        if contradictions:
            content = f"WARNING: {len(contradictions)} contradiction(s) detected in evidence."

        return DeliverableSection(
            heading="Evidence & Citations",
            content=content,
            items=items,
        )

    def _build_action_list(
        self,
        findings: list[dict[str, Any]],
        risk_report: dict[str, Any],
    ) -> DeliverableSection:
        """Build the action list section (for action_list deliverables)."""
        actions: list[dict[str, Any]] = []
        for f in sorted(findings, key=lambda x: {
            "CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4
        }.get(x.get("severity", "INFO"), 5)):
            for rec in f.get("recommended_actions", []):
                actions.append({
                    "priority": f.get("severity", "MEDIUM"),
                    "action": rec,
                    "finding": f.get("description", "")[:100],
                })

        return DeliverableSection(
            heading="Action Items",
            items=actions,
        )
