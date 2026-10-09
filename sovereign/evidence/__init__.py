"""Evidence — structured citation model, collection, and verification.

This package provides:

- ``Citation``: a single citation with full provenance (document, page,
  section, chunk, evidence text, support status).
- ``EvidenceCollector``: gathers evidence from the knowledge base for a
  query, with deduplication and source diversity.
- ``ContradictionDetector``: detects conflicting evidence across sources.
- ``CitationRenderer``: renders citations in multiple formats (markdown,
  inline, structured) for deliverables and API responses.

Every claim in SOVEREIGN must be traceable to evidence. This package is
the canonical implementation of that traceability.
"""

from sovereign.evidence.collector import EvidenceCollector
from sovereign.evidence.contradictions import ContradictionDetector
from sovereign.evidence.model import Citation, Contradiction, EvidenceReport, SupportStatus
from sovereign.evidence.renderer import CitationRenderer

__all__ = [
    "Citation",
    "CitationRenderer",
    "Contradiction",
    "ContradictionDetector",
    "EvidenceCollector",
    "EvidenceReport",
    "SupportStatus",
]
