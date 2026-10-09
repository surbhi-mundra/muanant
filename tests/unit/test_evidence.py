"""Tests for sovereign.evidence — citations, collector, contradictions, renderer."""

from __future__ import annotations

from sovereign.evidence.collector import EvidenceCollector
from sovereign.evidence.contradictions import ContradictionDetector
from sovereign.evidence.model import Citation, Contradiction, EvidenceReport
from sovereign.evidence.renderer import CitationRenderer
from sovereign.retrieval.service import RetrievalResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_result(
    chunk_id: str = "c1",
    document_id: str = "doc1",
    text: str = "test text",
    score: float = 0.5,
    page: int = 1,
    section_path: list[str] | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        score=score,
        page=page,
        section_path=section_path or ["Section 1"],
        chunk_index=0,
        block_kinds=["paragraph"],
    )


def _make_citation(
    citation_id: str = "cit_001",
    document_id: str = "doc1",
    document_filename: str = "report.txt",
    evidence_text: str = "pump maintenance required",
    page: int = 5,
    support_status: str = "SUPPORTED",
) -> Citation:
    return Citation(
        citation_id=citation_id,
        document_id=document_id,
        document_filename=document_filename,
        chunk_id="c1",
        page=page,
        section_path=["Chapter 1", "Section 2"],
        evidence_text=evidence_text,
        support_status=support_status,  # type: ignore[arg-type]
        relevance_score=0.8,
    )


# ---------------------------------------------------------------------------
# Citation model
# ---------------------------------------------------------------------------
class TestCitationModel:
    def test_section_label(self) -> None:
        """section_label should join section_path with ' > '."""
        cit = _make_citation()
        assert cit.section_label == "Chapter 1 > Section 2"

    def test_section_label_empty(self) -> None:
        """Empty section_path should produce '(no section)'."""
        cit = Citation(document_id="d1", section_path=[])
        assert cit.section_label == "(no section)"

    def test_source_label_with_page(self) -> None:
        """source_label should include filename, page, section."""
        cit = _make_citation(document_filename="report.txt", page=5)
        label = cit.source_label
        assert "report.txt" in label
        assert "p.5" in label
        assert "§Chapter 1 > Section 2" in label

    def test_source_label_without_page(self) -> None:
        """source_label should omit page when None."""
        cit = Citation(document_id="d1", document_filename="doc.txt", page=None)
        assert "p." not in cit.source_label
        assert "doc.txt" in cit.source_label

    def test_source_label_uses_doc_id_when_no_filename(self) -> None:
        """When filename is empty, use truncated document_id."""
        cit = Citation(document_id="0123456789ABCDEF", document_filename="")
        assert "0123456789AB" in cit.source_label  # first 12 chars


# ---------------------------------------------------------------------------
# EvidenceReport model
# ---------------------------------------------------------------------------
class TestEvidenceReport:
    def test_summary(self) -> None:
        """summary() should return correct counts."""
        report = EvidenceReport(
            query="test",
            citations=[
                _make_citation(citation_id="c1", support_status="SUPPORTED"),
                _make_citation(citation_id="c2", support_status="SUPPORTED"),
                _make_citation(citation_id="c3", support_status="PARTIALLY_SUPPORTED"),
                _make_citation(citation_id="c4", support_status="UNSUPPORTED"),
                _make_citation(citation_id="c5", support_status="CONFLICTING"),
            ],
            contradictions=[Contradiction(
                conflict_type="value_mismatch",
                description="test",
            )],
        )
        s = report.summary()
        assert s["citations"] == 5
        assert s["supported"] == 2
        assert s["partially_supported"] == 1
        assert s["unsupported"] == 1
        assert s["conflicting"] == 1
        assert s["contradictions"] == 1

    def test_unique_documents(self) -> None:
        """unique_documents should return distinct document IDs."""
        report = EvidenceReport(
            citations=[
                _make_citation(citation_id="c1", document_id="doc_a"),
                _make_citation(citation_id="c2", document_id="doc_b"),
                _make_citation(citation_id="c3", document_id="doc_a"),
            ]
        )
        assert len(report.unique_documents) == 2
        assert set(report.unique_documents) == {"doc_a", "doc_b"}

    def test_has_contradictions(self) -> None:
        """has_contradictions should be True when contradictions exist."""
        report = EvidenceReport(
            citations=[_make_citation()],
            contradictions=[Contradiction(
                conflict_type="value_mismatch", description="test"
            )],
        )
        assert report.has_contradictions is True

        report_empty = EvidenceReport(citations=[_make_citation()])
        assert report_empty.has_contradictions is False

    def test_counts(self) -> None:
        """Property counts should be correct."""
        report = EvidenceReport(
            citations=[
                _make_citation(citation_id="c1", support_status="SUPPORTED"),
                _make_citation(citation_id="c2", support_status="UNSUPPORTED"),
                _make_citation(citation_id="c3", support_status="CONFLICTING"),
            ]
        )
        assert report.supported_count == 1
        assert report.unsupported_count == 1
        assert report.conflicting_count == 1
        assert report.citation_count == 3


# ---------------------------------------------------------------------------
# EvidenceCollector
# ---------------------------------------------------------------------------
class TestEvidenceCollector:
    def test_collect_returns_citations(self) -> None:
        """collect() should return Citation objects."""
        results = [_make_result(chunk_id="c1"), _make_result(chunk_id="c2", document_id="doc2")]
        collector = EvidenceCollector()
        citations = collector.collect(results)
        assert len(citations) == 2
        assert all(isinstance(c, Citation) for c in citations)

    def test_collect_deduplicates_by_chunk_id(self) -> None:
        """Duplicate chunk_ids should be deduplicated."""
        results = [
            _make_result(chunk_id="c1", score=0.9),
            _make_result(chunk_id="c1", score=0.8),  # same chunk, different score
        ]
        collector = EvidenceCollector()
        citations = collector.collect(results)
        assert len(citations) == 1

    def test_collect_respects_max_total(self) -> None:
        """Should cap at max_total."""
        results = [
            _make_result(chunk_id=f"c{i}", document_id=f"doc{i}")
            for i in range(20)
        ]
        collector = EvidenceCollector(max_total=5, max_per_document=10)
        citations = collector.collect(results)
        assert len(citations) == 5

    def test_collect_respects_max_per_document(self) -> None:
        """Should cap citations per document."""
        results = [
            _make_result(chunk_id="c1", document_id="doc1"),
            _make_result(chunk_id="c2", document_id="doc1"),
            _make_result(chunk_id="c3", document_id="doc1"),
            _make_result(chunk_id="c4", document_id="doc2"),
        ]
        collector = EvidenceCollector(max_per_document=2, max_total=10)
        citations = collector.collect(results)
        doc1_count = sum(1 for c in citations if c.document_id == "doc1")
        doc2_count = sum(1 for c in citations if c.document_id == "doc2")
        assert doc1_count == 2
        assert doc2_count == 1

    def test_collect_filters_low_score(self) -> None:
        """Results below min_score should be filtered."""
        results = [
            _make_result(chunk_id="c1", score=0.5),
            _make_result(chunk_id="c2", score=0.001),
        ]
        collector = EvidenceCollector(min_score=0.01)
        citations = collector.collect(results)
        assert len(citations) == 1
        assert citations[0].chunk_id == "c1"

    def test_collect_empty_results(self) -> None:
        """Empty results should return empty."""
        collector = EvidenceCollector()
        citations = collector.collect([])
        assert citations == []

    def test_collect_assigns_citation_ids(self) -> None:
        """Citations should have stable citation_ids."""
        results = [_make_result(chunk_id="c1"), _make_result(chunk_id="c2")]
        collector = EvidenceCollector()
        citations = collector.collect(results)
        assert citations[0].citation_id == "cit_000"
        assert citations[1].citation_id == "cit_001"

    def test_collect_preserves_provenance(self) -> None:
        """Citations should carry page, section_path, document_id."""
        results = [
            _make_result(
                chunk_id="c1", document_id="doc1", page=7,
                section_path=["Ch1", "Sec2"],
            )
        ]
        collector = EvidenceCollector()
        citations = collector.collect(results)
        c = citations[0]
        assert c.document_id == "doc1"
        assert c.page == 7
        assert c.section_path == ["Ch1", "Sec2"]
        assert c.evidence_text == "test text"


# ---------------------------------------------------------------------------
# ContradictionDetector
# ---------------------------------------------------------------------------
class TestContradictionDetector:
    def test_no_contradictions_with_one_citation(self) -> None:
        """A single citation can't have contradictions."""
        detector = ContradictionDetector()
        contradictions = detector.detect([_make_citation()])
        assert contradictions == []

    def test_detect_value_mismatch(self) -> None:
        """Different numerical values for the same parameter should be detected."""
        detector = ContradictionDetector()
        citations = [
            _make_citation(
                citation_id="c1", evidence_text="The maximum pressure is 150 PSI for the pump."
            ),
            _make_citation(
                citation_id="c2", evidence_text="The maximum pressure is 200 PSI for the pump."
            ),
        ]
        contradictions = detector.detect(citations)
        value_conflicts = [c for c in contradictions if c.conflict_type == "value_mismatch"]
        assert len(value_conflicts) >= 1
        assert "150" in value_conflicts[0].description or "200" in value_conflicts[0].description

    def test_detect_contradictory_facts(self) -> None:
        """Contradictory status words (operational vs failed) should be detected."""
        detector = ContradictionDetector()
        citations = [
            _make_citation(
                citation_id="c1", evidence_text="Pump P-101 is operational and running normally."
            ),
            _make_citation(
                citation_id="c2",
                evidence_text="Pump P-101 is failed and requires immediate repair.",
            ),
        ]
        contradictions = detector.detect(citations)
        fact_conflicts = [c for c in contradictions if c.conflict_type == "contradictory_facts"]
        assert len(fact_conflicts) >= 1

    def test_no_false_positive_on_consistent_values(self) -> None:
        """Same value across sources should not trigger a contradiction."""
        detector = ContradictionDetector()
        citations = [
            _make_citation(citation_id="c1", evidence_text="The pressure is 150 PSI."),
            _make_citation(citation_id="c2", evidence_text="Pressure: 150 PSI confirmed."),
        ]
        contradictions = detector.detect(citations)
        value_conflicts = [c for c in contradictions if c.conflict_type == "value_mismatch"]
        assert len(value_conflicts) == 0

    def test_contradiction_includes_citation_ids(self) -> None:
        """Contradictions should link the conflicting citation IDs."""
        detector = ContradictionDetector()
        citations = [
            _make_citation(citation_id="c1", evidence_text="The system is operational."),
            _make_citation(citation_id="c2", evidence_text="The system is failed."),
        ]
        contradictions = detector.detect(citations)
        assert len(contradictions) >= 1
        assert len(contradictions[0].citation_ids) >= 2

    def test_detect_pass_fail(self) -> None:
        """Pass vs fail should be detected as contradictory."""
        detector = ContradictionDetector()
        citations = [
            _make_citation(citation_id="c1", evidence_text="Inspection result: pass."),
            _make_citation(citation_id="c2", evidence_text="Inspection result: fail."),
        ]
        contradictions = detector.detect(citations)
        assert len(contradictions) >= 1


# ---------------------------------------------------------------------------
# CitationRenderer
# ---------------------------------------------------------------------------
class TestCitationRenderer:
    def test_render_markdown_with_citations(self) -> None:
        """render_markdown should produce markdown with citations."""
        report = EvidenceReport(
            query="test query",
            citations=[_make_citation(citation_id="c1")],
        )
        renderer = CitationRenderer()
        md = renderer.render_markdown(report)
        assert "## Evidence & Citations" in md
        assert "report.txt" in md
        assert "SUPPORTED" in md

    def test_render_markdown_empty(self) -> None:
        """render_markdown on empty report should say no evidence."""
        report = EvidenceReport(query="test")
        renderer = CitationRenderer()
        md = renderer.render_markdown(report)
        assert "No evidence" in md

    def test_render_markdown_with_contradictions(self) -> None:
        """render_markdown should include contradictions section."""
        report = EvidenceReport(
            query="test",
            citations=[
                _make_citation(citation_id="c1"),
                _make_citation(citation_id="c2"),
            ],
            contradictions=[Contradiction(
                conflict_type="value_mismatch",
                description="Conflicting pressure values",
                citation_ids=["c1", "c2"],
                conflicting_texts=["150 PSI", "200 PSI"],
            )],
        )
        renderer = CitationRenderer()
        md = renderer.render_markdown(report)
        assert "Contradictions" in md or "contradict" in md.lower()
        assert "Conflicting pressure" in md

    def test_render_inline(self) -> None:
        """render_inline should produce [1] source; [2] source format."""
        citations = [
            _make_citation(citation_id="c1", document_filename="doc1.txt", page=5),
            _make_citation(citation_id="c2", document_filename="doc2.txt", page=10),
        ]
        renderer = CitationRenderer()
        inline = renderer.render_inline(citations)
        assert "[1]" in inline
        assert "[2]" in inline
        assert "doc1.txt" in inline
        assert "doc2.txt" in inline

    def test_render_inline_empty(self) -> None:
        """Empty citations should produce empty string."""
        renderer = CitationRenderer()
        assert renderer.render_inline([]) == ""

    def test_render_structured(self) -> None:
        """render_structured should produce a dict with all fields."""
        report = EvidenceReport(
            query="test",
            citations=[_make_citation(citation_id="c1")],
        )
        renderer = CitationRenderer()
        structured = renderer.render_structured(report)
        assert structured["query"] == "test"
        assert len(structured["citations"]) == 1
        assert structured["citations"][0]["citation_id"] == "c1"
        assert "summary" in structured
        assert "contradictions" in structured

    def test_render_citation_list_numbered(self) -> None:
        """render_citation_list should produce numbered list."""
        citations = [
            _make_citation(citation_id="c1", document_filename="doc1.txt"),
            _make_citation(citation_id="c2", document_filename="doc2.txt"),
        ]
        renderer = CitationRenderer()
        listing = renderer.render_citation_list(citations, numbered=True)
        assert "1." in listing
        assert "2." in listing

    def test_render_markdown_includes_summary(self) -> None:
        """render_markdown should include the summary stats."""
        report = EvidenceReport(
            query="test",
            citations=[
                _make_citation(citation_id="c1", support_status="SUPPORTED"),
                _make_citation(citation_id="c2", support_status="UNSUPPORTED"),
            ],
        )
        renderer = CitationRenderer()
        md = renderer.render_markdown(report)
        assert "2 citations" in md
        assert "1 supported" in md or "supported" in md.lower()
        assert "1 unsupported" in md or "unsupported" in md.lower()
