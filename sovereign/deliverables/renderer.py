"""Deliverable renderer — renders to markdown, HTML, structured JSON."""

from __future__ import annotations

from typing import Any

from sovereign.deliverables.model import Deliverable, DeliverableSection


class DeliverableRenderer:
    """Renders deliverables in multiple formats."""

    def render_markdown(self, deliverable: Deliverable) -> str:
        """Render as markdown."""
        lines: list[str] = []

        # Title
        lines.append(f"# {deliverable.metadata.title}")
        lines.append("")

        # Metadata
        lines.append(f"**Type:** {deliverable.metadata.deliverable_type}  ")
        lines.append(f"**Created:** {deliverable.metadata.created_at}  ")
        lines.append(f"**Author:** {deliverable.metadata.author}  ")
        if deliverable.metadata.project_id:
            lines.append(f"**Project:** {deliverable.metadata.project_id}  ")
        lines.append("")

        # Sections
        for section in deliverable.sections:
            lines.extend(self._render_section_markdown(section, level=2))

        # Citations footer
        if deliverable.citations:
            lines.append("---")
            lines.append(f"*{len(deliverable.citations)} citation(s)*")

        return "\n".join(lines)

    def _render_section_markdown(self, section: DeliverableSection, level: int) -> list[str]:
        """Render a section as markdown."""
        lines: list[str] = []
        lines.append(f"{'#' * level} {section.heading}")
        lines.append("")

        if section.content:
            lines.append(section.content)
            lines.append("")

        if section.items:
            for item in section.items:
                if "label" in item and "value" in item:
                    lines.append(f"- **{item['label']}**: {item['value']}")
                elif "description" in item:
                    severity = item.get("severity", "")
                    prefix = f"[{severity}] " if severity else ""
                    lines.append(f"- {prefix}{item['description']}")
                    if item.get("recommended_actions"):
                        for action in item["recommended_actions"]:
                            lines.append(f"  - → {action}")
                elif "action" in item:
                    priority = item.get("priority", "")
                    prefix = f"[{priority}] " if priority else ""
                    lines.append(f"- {prefix}{item['action']}")
                elif "source" in item:
                    status = item.get("status", "")
                    lines.append(f"- **{item['source']}** [{status}]")
                    if item.get("text"):
                        lines.append(f"  > {item['text'][:200]}")
                else:
                    lines.append(f"- {item}")
            lines.append("")

        for sub in section.subsections:
            lines.extend(self._render_section_markdown(sub, level + 1))

        return lines

    def render_html(self, deliverable: Deliverable) -> str:
        """Render as basic HTML."""
        html_parts: list[str] = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html><head><meta charset='utf-8'>")
        html_parts.append(f"<title>{deliverable.metadata.title}</title>")
        html_parts.append("<style>")
        html_parts.append("body { font-family: sans-serif; margin: 40px; }")
        html_parts.append("h1 { color: #333; }")
        html_parts.append("h2 { color: #555; margin-top: 30px; }")
        html_parts.append(".metadata { color: #666; font-size: 0.9em; }")
        html_parts.append(".citation { font-size: 0.85em; color: #666; }")
        html_parts.append(".critical { color: #c00; font-weight: bold; }")
        html_parts.append(".high { color: #c80; font-weight: bold; }")
        html_parts.append("</style>")
        html_parts.append("</head><body>")

        html_parts.append(f"<h1>{deliverable.metadata.title}</h1>")
        html_parts.append("<div class='metadata'>")
        html_parts.append(f"<p>Type: {deliverable.metadata.deliverable_type}</p>")
        html_parts.append(f"<p>Created: {deliverable.metadata.created_at}</p>")
        html_parts.append(f"<p>Author: {deliverable.metadata.author}</p>")
        html_parts.append("</div>")

        for section in deliverable.sections:
            html_parts.append(f"<h2>{section.heading}</h2>")
            if section.content:
                html_parts.append(f"<p>{section.content}</p>")
            if section.items:
                html_parts.append("<ul>")
                for item in section.items:
                    html_parts.append(f"<li>{self._render_item_html(item)}</li>")
                html_parts.append("</ul>")

        if deliverable.citations:
            html_parts.append(f"<p class='citation'>{len(deliverable.citations)} citation(s)</p>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _render_item_html(self, item: dict[str, Any]) -> str:
        """Render a single item as HTML."""
        if "label" in item and "value" in item:
            return f"<strong>{item['label']}</strong>: {item['value']}"
        if "description" in item:
            severity = item.get("severity", "")
            cls = severity.lower() if severity else ""
            prefix = f"<span class='{cls}'>[{severity}]</span> " if severity else ""
            return f"{prefix}{item['description']}"
        if "action" in item:
            priority = item.get("priority", "")
            cls = priority.lower() if priority else ""
            return f"<span class='{cls}'>[{priority}]</span> {item['action']}"
        if "source" in item:
            status = item.get("status", "")
            return f"<strong>{item['source']}</strong> [{status}]"
        return str(item)

    def render_structured(self, deliverable: Deliverable) -> dict[str, Any]:
        """Render as a JSON-serializable dict."""
        return deliverable.model_dump()
