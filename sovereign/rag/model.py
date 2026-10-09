"""RAG pipeline types — Verdict, RAGResponse, EvidenceRef, Claim.

These are the typed inputs/outputs of the 9-stage pipeline. Every
downstream subsystem (agents, deliverables, API) consumes these types.

Key design decision: ``Verdict`` is a first-class type. "I don't have
sufficient evidence" is NOT an error — it's a successful, explicit
system response. The pipeline returns it whenever evidence verification
fails, rather than letting the LLM hallucinate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Evidence & provenance
# ---------------------------------------------------------------------------
SupportStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONFLICTING"]


class EvidenceRef(BaseModel):
    """A reference to a piece of evidence in the knowledge base.

    Every claim in a RAG response carries one or more EvidenceRefs.
    This is the citation unit — it flows through to deliverable rendering.
    """

    document_id: str
    chunk_id: str = ""
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)
    text: str = ""  # the evidence text (the chunk or span that supports the claim)

    @property
    def section_label(self) -> str:
        return " > ".join(self.section_path) if self.section_path else "(no section)"


class Claim(BaseModel):
    """A single claim in a RAG response, with evidence and support status.

    The evidence verification stage (stage 8) sets ``support_status`` after
    checking the claim against the evidence. Deliverables render claims
    with their status so readers know what's grounded vs speculative.
    """

    text: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    support_status: SupportStatus = "SUPPORTED"


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
VerdictKind = Literal[
    "answered",             # the query was answered with grounded evidence
    "insufficient_evidence",  # not enough evidence to answer
    "out_of_scope",          # query is outside the KB's domain
]


class Verdict(BaseModel):
    """The pipeline's final verdict on a query.

    ``answered``: the LLM produced a grounded answer with verified claims.
    ``insufficient_evidence``: retrieval returned too little, or evidence
        verification failed. The system explicitly says "I don't know."
    ``out_of_scope``: the query was classified as outside the KB's domain
        (e.g. asking about weather when the KB is about industrial equipment).
    """

    kind: VerdictKind
    message: str = ""

    @classmethod
    def answered(cls) -> Verdict:
        return cls(kind="answered", message="Query answered with grounded evidence.")

    @classmethod
    def insufficient_evidence(cls) -> Verdict:
        return cls(
            kind="insufficient_evidence",
            message="I don't have sufficient evidence to answer this.",
        )

    @classmethod
    def out_of_scope(cls) -> Verdict:
        return cls(
            kind="out_of_scope",
            message="This query is outside the scope of the available knowledge base.",
        )


# ---------------------------------------------------------------------------
# Query understanding (stage 1)
# ---------------------------------------------------------------------------
QueryIntent = Literal[
    "factual",       # looking for a specific fact
    "procedural",    # how-to / process question
    "analytical",    # requires reasoning across multiple sources
    "comparative",   # comparing options/entities
    "definitional",  # what is X
    "conversational", # follow-up in a conversation
]


class QueryAnalysis(BaseModel):
    """Output of stage 1 (query understanding)."""

    intent: QueryIntent = "factual"
    # Key terms extracted from the query (for keyword search emphasis)
    key_terms: list[str] = Field(default_factory=list)
    # Constraints extracted (e.g. "in 2024", "for pump P-101")
    constraints: dict[str, str] = Field(default_factory=dict)
    # Whether the query looks like it needs external research
    needs_external: bool = False
    # Reformulated query strings for stage 2
    rewritten_queries: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline response
# ---------------------------------------------------------------------------
class RAGResponse(BaseModel):
    """The complete output of the 9-stage RAG pipeline.

    This is what the API returns and what agents/deliverables consume.
    """

    # The user's original query
    query: str

    # The verdict (answered / insufficient_evidence / out_of_scope)
    verdict: Verdict

    # The answer text (empty if verdict != answered)
    answer: str = ""

    # Claims extracted from the answer, each with evidence + support status
    claims: list[Claim] = Field(default_factory=list)

    # All evidence chunks used (for transparency / "show sources")
    evidence: list[EvidenceRef] = Field(default_factory=list)

    # Full evidence report with citations + contradictions (Phase 6)
    # Typed as object to avoid circular import; it's an EvidenceReport.
    evidence_report: object | None = None

    # Pipeline metadata for debugging + audit
    pipeline_trace: dict[str, object] = Field(default_factory=dict)

    @property
    def is_answered(self) -> bool:
        return self.verdict.kind == "answered"

    @property
    def has_contradictions(self) -> bool:
        """True if the evidence report contains detected contradictions."""
        if self.evidence_report is None:
            return False
        # EvidenceReport has_contradictions property
        return getattr(self.evidence_report, "has_contradictions", False)

    @property
    def has_sufficient_evidence(self) -> bool:
        return self.verdict.kind != "insufficient_evidence"
