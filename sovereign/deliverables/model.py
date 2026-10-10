"""Deliverable model — the canonical report structure.

A ``Deliverable`` is a structured report with sections, metadata, and
citations. It's the output of the deliverable agent and the input to
the exporters (PDF, DOCX, XLSX, CSV, JSON).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DeliverableType = Literal[
    "inspection_report",
    "maintenance_report",
    "incident_report",
    "executive_summary",
    "action_list",
    "risk_assessment",
    "summary",
    "custom",
]


class DeliverableMetadata(BaseModel):
    """Metadata about a deliverable."""

    title: str = ""
    deliverable_type: DeliverableType = "summary"
    created_at: str = ""
    project_id: str = ""
    query: str = ""
    author: str = "SOVEREIGN AI Workbench"
    version: str = "1.0"


class DeliverableSection(BaseModel):
    """A section of a deliverable report.

    Sections are the building blocks of a deliverable. Each has a heading,
    content (text), and optional items (for lists/tables).
    """

    heading: str
    content: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    subsections: list[DeliverableSection] = Field(default_factory=list)

    @property
    def has_items(self) -> bool:
        return len(self.items) > 0


class Deliverable(BaseModel):
    """A complete deliverable report.

    Contains metadata, ordered sections, and optional citations.
    This is what gets exported to PDF/DOCX/XLSX/CSV/JSON.
    """

    metadata: DeliverableMetadata
    sections: list[DeliverableSection] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    metadata_extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.metadata.title

    @property
    def section_count(self) -> int:
        return len(self.sections)

    def get_section(self, heading: str) -> DeliverableSection | None:
        """Find a section by heading (case-insensitive)."""
        for s in self.sections:
            if s.heading.lower() == heading.lower():
                return s
        return None
