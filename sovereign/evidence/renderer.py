"""Citation renderer — renders evidence in multiple formats for deliverables.

Produces:
1. **Markdown** — human-readable, used in reports and the workbench UI.
2. **Inline** — compact [1], [2] style references for answer text.
3. **Structured** — JSON-serializable dict for API responses.

The renderer is used by the deliverable generator (Phase 10) and the
RAG API to produce citation output.
"""

from __future__ import annotations

from sovereign.evidence.model import Citation, EvidenceReport


class CitationRenderer:
    """Renders citations and evidence reports in multiple formats."""

    def render_markdown(self, report: EvidenceReport) -> str:
        """Render a full evidence report as markdown.

        Includes: citation list with support status, contradictions section.
        """
        lines: list[str] = []

        lines.append("## Evidence & Citations")
        lines.append("")

        if not report.citations:
            lines.append("*No evidence was found for this query.*")
            return "\n".join(lines)

        # Summary
        s = report.summary()
        lines.append(
            f"**Summary:** {s['citations']} citations from "
            f"{s['unique_documents']} document(s) — "
            f"{s['supported']} supported, "
            f"{s['partially_supported']} partially supported, "
            f"{s['unsupported']} unsupported, "
            f"{s['conflicting']} conflicting"
        )
        lines.append("")

        # Citations
        lines.append("### Sources")
        lines.append("")
        for i, cit in enumerate(report.citations, 1):
            status_icon = _status_icon(cit.support_status)
            lines.append(f"{i}. {status_icon} **{cit.source_label}**")
            lines.append(f"   - Status: `{cit.support_status}`")
            if cit.support_note:
                lines.append(f"   - Note: {cit.support_note}")
            lines.append(f"   - Evidence: > {cit.evidence_text[:300]}")
            if len(cit.evidence_text) > 300:
                lines.append(f"   - *(truncated, full length: {len(cit.evidence_text)} chars)*")
            lines.append("")

        # Contradictions
        if report.has_contradictions:
            lines.append("### ⚠️ Detected Contradictions")
            lines.append("")
            for con in report.contradictions:
                lines.append(f"- **{con.conflict_type}**: {con.description}")
                for text in con.conflicting_texts:
                    lines.append(f"  - {text}")
                lines.append("")

        return "\n".join(lines)

    def render_inline(
        self, citations: list[Citation]
    ) -> str:
        """Render citations as inline reference markers.

        Returns a string like ``[1] filename, p.5; [2] filename2, p.12``
        suitable for appending to an answer.
        """
        if not citations:
            return ""

        parts: list[str] = []
        for i, cit in enumerate(citations, 1):
            parts.append(f"[{i}] {cit.source_label}")

        return "; ".join(parts)

    def render_structured(
        self, report: EvidenceReport
    ) -> dict[str, object]:
        """Render as a JSON-serializable dict for API responses."""
        return {
            "query": report.query,
            "summary": report.summary(),
            "citations": [
                {
                    "citation_id": c.citation_id,
                    "document_id": c.document_id,
                    "document_filename": c.document_filename,
                    "chunk_id": c.chunk_id,
                    "page": c.page,
                    "section_path": c.section_path,
                    "section_label": c.section_label,
                    "source_label": c.source_label,
                    "evidence_text": c.evidence_text,
                    "support_status": c.support_status,
                    "support_note": c.support_note,
                    "relevance_score": c.relevance_score,
                }
                for c in report.citations
            ],
            "contradictions": [
                {
                    "conflict_type": con.conflict_type,
                    "description": con.description,
                    "citation_ids": con.citation_ids,
                    "conflicting_texts": con.conflicting_texts,
                }
                for con in report.contradictions
            ],
        }

    def render_citation_list(
        self, citations: list[Citation], numbered: bool = True
    ) -> str:
        """Render a simple numbered or bulleted citation list."""
        lines: list[str] = []
        for i, cit in enumerate(citations, 1) if numbered else enumerate(citations, 0):
            prefix = f"{i}." if numbered else "•"
            status = f" [{cit.support_status}]" if cit.support_status != "SUPPORTED" else ""
            lines.append(f"{prefix} {cit.source_label}{status}")
        return "\n".join(lines)


def _status_icon(status: str) -> str:
    """Return a text icon for a support status."""
    icons = {
        "SUPPORTED": "✓",
        "PARTIALLY_SUPPORTED": "◐",
        "UNSUPPORTED": "✗",
        "CONFLICTING": "⚠",
    }
    return icons.get(status, "?")
