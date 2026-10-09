"""Deliverable exporter — exports to PDF, DOCX, XLSX, CSV, JSON.

Each format has its own export method. All exporters preserve citation
references so reports maintain traceability.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from sovereign.deliverables.model import Deliverable
from sovereign.deliverables.renderer import DeliverableRenderer


class DeliverableExporter:
    """Exports deliverables to multiple file formats.

    Usage::

        exporter = DeliverableExporter()
        exporter.to_json(deliverable, Path("report.json"))
        exporter.to_markdown(deliverable, Path("report.md"))
        exporter.to_csv(deliverable, Path("findings.csv"))
    """

    def __init__(self) -> None:
        self._renderer = DeliverableRenderer()

    def to_json(self, deliverable: Deliverable, path: Path | None = None) -> str:
        """Export as JSON. Returns JSON string; writes to path if given."""
        data = self._renderer.render_structured(deliverable)
        json_str = json.dumps(data, indent=2, default=str)
        if path:
            path.write_text(json_str, encoding="utf-8")
        return json_str

    def to_markdown(self, deliverable: Deliverable, path: Path | None = None) -> str:
        """Export as markdown. Returns markdown string; writes to path if given."""
        md = self._renderer.render_markdown(deliverable)
        if path:
            path.write_text(md, encoding="utf-8")
        return md

    def to_html(self, deliverable: Deliverable, path: Path | None = None) -> str:
        """Export as HTML."""
        html = self._renderer.render_html(deliverable)
        if path:
            path.write_text(html, encoding="utf-8")
        return html

    def to_csv(self, deliverable: Deliverable, path: Path | None = None) -> str:
        """Export findings as CSV. Returns CSV string; writes to path if given."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["Finding ID", "Description", "Severity", "Category", "Source", "Recommended Actions"])

        # Findings
        for finding in deliverable.findings:
            actions = "; ".join(finding.get("recommended_actions", []))
            writer.writerow([
                finding.get("finding_id", ""),
                finding.get("description", ""),
                finding.get("severity", ""),
                finding.get("category", ""),
                finding.get("source", ""),
                actions,
            ])

        csv_str = output.getvalue()
        if path:
            path.write_text(csv_str, encoding="utf-8")
        return csv_str

    def to_xlsx(self, deliverable: Deliverable, path: Path | None = None) -> bytes:
        """Export as XLSX with multiple sheets (Summary, Findings, Citations)."""
        import openpyxl  # type: ignore[import-untyped]

        wb = openpyxl.Workbook()

        # Sheet 1: Summary
        ws_summary = wb.active
        ws_summary.title = "Summary"
        ws_summary.append(["Field", "Value"])
        ws_summary.append(["Title", deliverable.metadata.title])
        ws_summary.append(["Type", deliverable.metadata.deliverable_type])
        ws_summary.append(["Created", deliverable.metadata.created_at])
        ws_summary.append(["Project", deliverable.metadata.project_id])
        ws_summary.append(["Author", deliverable.metadata.author])
        ws_summary.append(["Sections", str(deliverable.section_count)])
        ws_summary.append(["Findings", str(len(deliverable.findings))])
        ws_summary.append(["Citations", str(len(deliverable.citations))])

        # Sheet 2: Sections
        ws_sections = wb.create_sheet("Sections")
        ws_sections.append(["Heading", "Content"])
        for section in deliverable.sections:
            ws_sections.append([section.heading, section.content])

        # Sheet 3: Findings
        ws_findings = wb.create_sheet("Findings")
        ws_findings.append(["ID", "Description", "Severity", "Category", "Source", "Actions"])
        for finding in deliverable.findings:
            actions = "; ".join(finding.get("recommended_actions", []))
            ws_findings.append([
                finding.get("finding_id", ""),
                finding.get("description", ""),
                finding.get("severity", ""),
                finding.get("category", ""),
                finding.get("source", ""),
                actions,
            ])

        # Sheet 4: Citations
        ws_citations = wb.create_sheet("Citations")
        ws_citations.append(["Source", "Status", "Evidence Text"])
        for cit in deliverable.citations:
            ws_citations.append([
                cit.get("source_label", cit.get("document_id", "")),
                cit.get("support_status", ""),
                cit.get("evidence_text", "")[:500],
            ])

        # Write to bytes
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        if path:
            path.write_bytes(xlsx_bytes)

        return xlsx_bytes

    def to_docx(self, deliverable: Deliverable, path: Path | None = None) -> bytes:
        """Export as DOCX."""
        import docx

        doc = docx.Document()

        # Title
        doc.add_heading(deliverable.metadata.title, 0)

        # Metadata
        doc.add_paragraph(f"Type: {deliverable.metadata.deliverable_type}")
        doc.add_paragraph(f"Created: {deliverable.metadata.created_at}")
        doc.add_paragraph(f"Author: {deliverable.metadata.author}")
        if deliverable.metadata.project_id:
            doc.add_paragraph(f"Project: {deliverable.metadata.project_id}")

        # Sections
        for section in deliverable.sections:
            doc.add_heading(section.heading, level=1)

            if section.content:
                doc.add_paragraph(section.content)

            if section.items:
                for item in section.items:
                    if "label" in item and "value" in item:
                        doc.add_paragraph(f"{item['label']}: {item['value']}")
                    elif "description" in item:
                        severity = item.get("severity", "")
                        prefix = f"[{severity}] " if severity else ""
                        doc.add_paragraph(f"{prefix}{item['description']}", style="List Bullet")
                    elif "action" in item:
                        priority = item.get("priority", "")
                        prefix = f"[{priority}] " if priority else ""
                        doc.add_paragraph(f"{prefix}{item['action']}", style="List Bullet")
                    elif "source" in item:
                        status = item.get("status", "")
                        doc.add_paragraph(
                            f"{item['source']} [{status}]",
                            style="List Bullet",
                        )

        # Citations footer
        if deliverable.citations:
            doc.add_paragraph(f"\n{len(deliverable.citations)} citation(s)")

        # Write to bytes
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        if path:
            path.write_bytes(docx_bytes)

        return docx_bytes

    def to_pdf(self, deliverable: Deliverable, path: Path | None = None) -> bytes:
        """Export as PDF using reportlab."""
        from reportlab.lib import colors  # type: ignore[import-untyped]
        from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
        from reportlab.lib.styles import (  # type: ignore[import-untyped]
            getSampleStyleSheet,
        )
        from reportlab.lib.units import inch  # type: ignore[import-untyped]
        from reportlab.platypus import (  # type: ignore[import-untyped]
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=inch, bottomMargin=inch)

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        story: list[Any] = []

        # Title
        story.append(Paragraph(deliverable.metadata.title, title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Metadata
        meta_data = [
            ["Type:", deliverable.metadata.deliverable_type],
            ["Created:", deliverable.metadata.created_at],
            ["Author:", deliverable.metadata.author],
        ]
        if deliverable.metadata.project_id:
            meta_data.append(["Project:", deliverable.metadata.project_id])

        meta_table = Table(meta_data, colWidths=[1.5 * inch, 4 * inch])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.3 * inch))

        # Sections
        for section in deliverable.sections:
            story.append(Paragraph(section.heading, heading_style))
            story.append(Spacer(1, 0.1 * inch))

            if section.content:
                story.append(Paragraph(section.content, normal_style))
                story.append(Spacer(1, 0.1 * inch))

            if section.items:
                for item in section.items:
                    if "label" in item and "value" in item:
                        story.append(Paragraph(
                            f"<b>{item['label']}:</b> {item['value']}",
                            normal_style,
                        ))
                    elif "description" in item:
                        severity = item.get("severity", "")
                        prefix = f"[{severity}] " if severity else ""
                        story.append(Paragraph(
                            f"• {prefix}{item['description']}",
                            normal_style,
                        ))
                    elif "action" in item:
                        priority = item.get("priority", "")
                        prefix = f"[{priority}] " if priority else ""
                        story.append(Paragraph(
                            f"• {prefix}{item['action']}",
                            normal_style,
                        ))
                    elif "source" in item:
                        status = item.get("status", "")
                        story.append(Paragraph(
                            f"• <b>{item['source']}</b> [{status}]",
                            normal_style,
                        ))

                story.append(Spacer(1, 0.1 * inch))

        # Citations footer
        if deliverable.citations:
            story.append(Spacer(1, 0.3 * inch))
            story.append(Paragraph(
                f"<i>{len(deliverable.citations)} citation(s)</i>",
                normal_style,
            ))

        doc.build(story)
        pdf_bytes = buf.getvalue()

        if path:
            path.write_bytes(pdf_bytes)

        return pdf_bytes
