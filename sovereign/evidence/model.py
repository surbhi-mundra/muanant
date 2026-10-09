"""Evidence model — Citation, EvidenceReport, and related types.

A ``Citation`` is the canonical unit of provenance in SOVEREIGN. Every
claim in a RAG response, agent output, or deliverable carries one or more
Citations. Each Citation links to a specific chunk in a specific document,
with the exact text that supports (or contradicts) the claim.

The ``EvidenceReport`` bundles all citations for a single query/response,
including detected contradictions. It's what gets stored, audited, and
rendered into deliverables.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SupportStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONFLICTING"]

ConflictType = Literal[
    "value_mismatch",      # two sources give different values for the same thing
    "contradictory_facts", # sources directly contradict each other
    "temporal_conflict",   # newer source supersedes older
    "scope_conflict",      # sources apply to different scopes/models
]


class Citation(BaseModel):
    """A single citation linking a claim to evidence.

    This is the traceability unit. It carries:
    - Full provenance (document_id, page, section_path, chunk_id)
    - The evidence text (the actual words from the source)
    - The support status (how well this evidence supports the claim)
    - An optional note explaining the support assessment
    """

    citation_id: str = ""  # stable ID for referencing within a report
    document_id: str
    document_filename: str = ""  # human-readable, for rendering
    chunk_id: str = ""
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)
    evidence_text: str = ""
    support_status: SupportStatus = "SUPPORTED"
    support_note: str = ""  # explanation of why this status was assigned
    relevance_score: float = 0.0  # reranker score, for ranking citations

    @property
    def section_label(self) -> str:
        """Human-readable section path for citation rendering."""
        return " > ".join(self.section_path) if self.section_path else "(no section)"

    @property
    def source_label(self) -> str:
        """Human-readable source reference for inline citations.

        Format: ``filename, p.5, §Section > Subsection``
        """
        parts = [self.document_filename or self.document_id[:12]]
        if self.page:
            parts.append(f"p.{self.page}")
        if self.section_path:
            parts.append(f"§{self.section_label}")
        return ", ".join(parts)


class Contradiction(BaseModel):
    """A detected contradiction between two or more citations.

    The contradiction detector finds cases where evidence sources disagree.
    Each contradiction links the conflicting citations and classifies the
    type of conflict.
    """

    conflict_type: ConflictType
    description: str
    citation_ids: list[str] = Field(default_factory=list)
    # The specific text from each source that conflicts
    conflicting_texts: list[str] = Field(default_factory=list)


class EvidenceReport(BaseModel):
    """Complete evidence bundle for a single query/response.

    Contains all citations, detected contradictions, and a summary.
    This is what gets stored alongside a RAG response and rendered into
    deliverables.
    """

    query: str = ""
    citations: list[Citation] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)

    @property
    def citation_count(self) -> int:
        return len(self.citations)

    @property
    def supported_count(self) -> int:
        return sum(1 for c in self.citations if c.support_status == "SUPPORTED")

    @property
    def partially_supported_count(self) -> int:
        return sum(1 for c in self.citations if c.support_status == "PARTIALLY_SUPPORTED")

    @property
    def unsupported_count(self) -> int:
        return sum(1 for c in self.citations if c.support_status == "UNSUPPORTED")

    @property
    def conflicting_count(self) -> int:
        return sum(1 for c in self.citations if c.support_status == "CONFLICTING")

    @property
    def has_contradictions(self) -> bool:
        return len(self.contradictions) > 0

    @property
    def unique_documents(self) -> list[str]:
        """List of unique document IDs cited in this report."""
        return list({c.document_id for c in self.citations})

    def citations_for_claim(self, claim_text: str) -> list[Citation]:
        """Return citations associated with a specific claim (by text match)."""
        # Citations don't directly link to claims; this is a convenience
        # for rendering. In practice, claims carry their own evidence list.
        return [c for c in self.citations if claim_text.lower() in c.evidence_text.lower()]

    def summary(self) -> dict[str, int]:
        """Return a summary dict for audit/logging."""
        return {
            "citations": self.citation_count,
            "supported": self.supported_count,
            "partially_supported": self.partially_supported_count,
            "unsupported": self.unsupported_count,
            "conflicting": self.conflicting_count,
            "contradictions": len(self.contradictions),
            "unique_documents": len(self.unique_documents),
        }
