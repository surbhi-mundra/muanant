"""Tests for sovereign.deliverables — builder, renderer, exporter."""

from __future__ import annotations

import json
from pathlib import Path

from sovereign.deliverables.builder import DeliverableBuilder
from sovereign.deliverables.exporter import DeliverableExporter
from sovereign.deliverables.model import Deliverable
from sovereign.deliverables.renderer import DeliverableRenderer


def _make_test_deliverable() -> Deliverable:
    """Build a test deliverable with findings + citations."""
    builder = DeliverableBuilder()
    return builder.build(
        deliverable_type="inspection_report",
        query="What is the condition of pump P-101?",
        project_id="proj_test",
        rag_response={
            "answer": "Pump P-101 shows bearing wear and requires maintenance.",
            "verdict": {"kind": "answered"},
        },
        findings=[
            {
                "finding_id": "f1",
                "description": "Bearing wear detected on pump P-101.",
                "severity": "HIGH",
                "category": "mechanical",
                "source": "evidence",
                "recommended_actions": ["Replace bearing within 7 days.", "Increase monitoring."],
            },
        ],
        evidence_report={
            "citations": [
                {
                    "citation_id": "c1",
                    "document_id": "doc1",
                    "source_label": "inspection.txt",
                    "support_status": "SUPPORTED",
                    "evidence_text": "Bearing wear confirmed during inspection.",
                }
            ],
            "contradictions": [],
        },
        risk_report={
            "overall_risk_score": 75,
            "risk_level": "HIGH",
            "total_findings": 1,
            "summary": "Risk Assessment: HIGH (score: 75/100)",
            "recommendations": ["Schedule corrective action within 7 days."],
        },
    )


class TestDeliverableBuilder:
    def test_build_basic_deliverable(self) -> None:
        """Builder should produce a Deliverable with sections."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="summary",
            query="test query",
            rag_response={"answer": "test answer", "verdict": {"kind": "answered"}},
        )
        assert isinstance(deliverable, Deliverable)
        assert deliverable.section_count > 0
        assert deliverable.title

    def test_build_with_findings(self) -> None:
        """Findings should produce a Findings section."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="risk_assessment",
            query="test",
            findings=[{"description": "test finding", "severity": "HIGH"}],
        )
        findings_section = deliverable.get_section("Findings")
        assert findings_section is not None
        assert len(findings_section.items) == 1

    def test_build_with_evidence(self) -> None:
        """Evidence report should produce a Citations section."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="summary",
            query="test",
            evidence_report={
                "citations": [{"source_label": "doc1.txt", "support_status": "SUPPORTED"}],
                "contradictions": [],
            },
        )
        assert len(deliverable.citations) == 1
        evidence_section = deliverable.get_section("Evidence & Citations")
        assert evidence_section is not None

    def test_build_includes_executive_summary(self) -> None:
        """Every deliverable should have an Executive Summary section."""
        builder = DeliverableBuilder()
        deliverable = builder.build(deliverable_type="summary", query="test")
        assert deliverable.get_section("Executive Summary") is not None

    def test_build_action_list_type(self) -> None:
        """Action list type should produce an Action Items section."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="action_list",
            query="test",
            findings=[{
                "description": "fix bearing",
                "severity": "HIGH",
                "recommended_actions": ["Replace bearing"],
            }],
        )
        assert deliverable.get_section("Action Items") is not None

    def test_build_includes_risk_section(self) -> None:
        """Risk report should produce a Risk Assessment section."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="risk_assessment",
            query="test",
            risk_report={"overall_risk_score": 75, "risk_level": "HIGH", "summary": "test"},
        )
        assert deliverable.get_section("Risk Assessment") is not None

    def test_build_title_includes_type(self) -> None:
        """Title should include the deliverable type label."""
        builder = DeliverableBuilder()
        deliverable = builder.build(
            deliverable_type="inspection_report",
            query="test query",
        )
        assert "Inspection Report" in deliverable.title

    def test_build_has_deliverable_id(self) -> None:
        """Deliverable should have a unique ID in metadata_extra."""
        builder = DeliverableBuilder()
        deliverable = builder.build(deliverable_type="summary", query="test")
        assert deliverable.metadata_extra.get("deliverable_id")


class TestDeliverableRenderer:
    def test_render_markdown(self) -> None:
        """Markdown should include title and sections."""
        deliverable = _make_test_deliverable()
        renderer = DeliverableRenderer()
        md = renderer.render_markdown(deliverable)
        assert "# " in md
        assert "Executive Summary" in md
        assert "Findings" in md

    def test_render_markdown_includes_findings(self) -> None:
        """Markdown should include finding descriptions."""
        deliverable = _make_test_deliverable()
        renderer = DeliverableRenderer()
        md = renderer.render_markdown(deliverable)
        assert "Bearing wear" in md
        assert "[HIGH]" in md

    def test_render_html(self) -> None:
        """HTML should be valid."""
        deliverable = _make_test_deliverable()
        renderer = DeliverableRenderer()
        html = renderer.render_html(deliverable)
        assert "<html>" in html
        assert "</html>" in html
        assert "Bearing wear" in html

    def test_render_structured(self) -> None:
        """Structured output should be a dict."""
        deliverable = _make_test_deliverable()
        renderer = DeliverableRenderer()
        structured = renderer.render_structured(deliverable)
        assert isinstance(structured, dict)
        assert "metadata" in structured
        assert "sections" in structured


class TestDeliverableExporter:
    def test_to_json(self) -> None:
        """JSON export should be valid JSON."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        json_str = exporter.to_json(deliverable)
        parsed = json.loads(json_str)
        assert parsed["metadata"]["title"]

    def test_to_markdown(self) -> None:
        """Markdown export should produce text."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        md = exporter.to_markdown(deliverable)
        assert isinstance(md, str)
        assert "Bearing wear" in md

    def test_to_csv(self) -> None:
        """CSV export should include findings."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        csv_str = exporter.to_csv(deliverable)
        assert "Description" in csv_str
        assert "Bearing wear" in csv_str
        assert "HIGH" in csv_str

    def test_to_xlsx(self) -> None:
        """XLSX export should produce bytes."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        xlsx_bytes = exporter.to_xlsx(deliverable)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 0
        # XLSX magic bytes (ZIP)
        assert xlsx_bytes[:2] == b"PK"

    def test_to_docx(self) -> None:
        """DOCX export should produce bytes."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        docx_bytes = exporter.to_docx(deliverable)
        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 0
        # DOCX is also a ZIP
        assert docx_bytes[:2] == b"PK"

    def test_to_pdf(self) -> None:
        """PDF export should produce bytes."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        pdf_bytes = exporter.to_pdf(deliverable)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF magic
        assert pdf_bytes[:4] == b"%PDF"

    def test_to_html(self) -> None:
        """HTML export should produce HTML."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        html = exporter.to_html(deliverable)
        assert "<html>" in html

    def test_json_writes_to_file(self, tmp_path: Path) -> None:
        """JSON export should write to a file."""
        deliverable = _make_test_deliverable()
        exporter = DeliverableExporter()
        path = tmp_path / "report.json"
        exporter.to_json(deliverable, path)
        assert path.exists()
        content = path.read_text()
        assert json.loads(content)
