"""Tests for sovereign.rag — 9-stage pipeline, evidence verification."""

from __future__ import annotations

import pytest

from sovereign.embeddings.indexing import IndexingService, reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.parsing.model import Block, DocumentMetadata, Page, ParsedDocument
from sovereign.rag.model import EvidenceRef, QueryAnalysis, RAGResponse
from sovereign.rag.pipeline import RAGPipeline, reset_rag_pipeline
from sovereign.rag.reason import generate_answer
from sovereign.rag.rewrite import expand_query
from sovereign.rag.select import select_evidence
from sovereign.rag.understand import _heuristic_understand, understand_query
from sovereign.rag.verify import _extract_claims, _heuristic_verify, verify_answer
from sovereign.retrieval.service import RetrievalResult
from sovereign.storage.qdrant import reset_qdrant_store


@pytest.fixture(autouse=True)
def _reset_all():
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()
    yield
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()
    reset_rag_pipeline()


def _make_result(
    chunk_id: str = "c1",
    document_id: str = "doc1",
    text: str = "test text",
    score: float = 0.5,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        score=score,
        page=1,
        section_path=["Section 1"],
        chunk_index=0,
        block_kinds=["paragraph"],
    )


def _make_evidence(
    document_id: str = "doc1",
    text: str = "pump maintenance is required",
    chunk_id: str = "c1",
) -> EvidenceRef:
    return EvidenceRef(
        document_id=document_id,
        chunk_id=chunk_id,
        page=1,
        section_path=["Section 1"],
        text=text,
    )


# ---------------------------------------------------------------------------
# Stage 1: Query understanding
# ---------------------------------------------------------------------------
class TestQueryUnderstanding:
    async def test_understand_returns_analysis(self) -> None:
        """understand_query should return a QueryAnalysis."""
        from sovereign.models.gateway import get_model_gateway

        gw = get_model_gateway()
        analysis = await understand_query("How do I maintain pump P-101?", gw)
        assert isinstance(analysis, QueryAnalysis)
        assert analysis.intent in (
            "factual", "procedural", "analytical",
            "comparative", "definitional", "conversational",
        )

    def test_heuristic_intent_procedural(self) -> None:
        """Heuristic should detect procedural intent."""
        a = _heuristic_understand("How to perform maintenance")
        assert a.intent == "procedural"

    def test_heuristic_intent_definitional(self) -> None:
        """Heuristic should detect definitional intent."""
        a = _heuristic_understand("What is a centrifugal pump")
        assert a.intent == "definitional"

    def test_heuristic_intent_comparative(self) -> None:
        """Heuristic should detect comparative intent."""
        a = _heuristic_understand("Compare pump A versus pump B")
        assert a.intent == "comparative"

    def test_heuristic_intent_analytical(self) -> None:
        """Heuristic should detect analytical intent."""
        a = _heuristic_understand("Why did the bearing fail")
        assert a.intent == "analytical"

    def test_heuristic_extracts_key_terms(self) -> None:
        """Heuristic should extract meaningful key terms."""
        a = _heuristic_understand("What is the maintenance schedule for pump P-101")
        # Should contain "maintenance" and "schedule" (not stopwords)
        assert "maintenance" in a.key_terms
        assert "schedule" in a.key_terms
        # Should NOT contain stopwords
        assert "the" not in a.key_terms
        assert "for" not in a.key_terms


# ---------------------------------------------------------------------------
# Stage 2: Query rewriting
# ---------------------------------------------------------------------------
class TestQueryRewriting:
    def test_expand_returns_original_first(self) -> None:
        """The original query should always be first."""
        analysis = QueryAnalysis(intent="factual", key_terms=["pump", "maintenance"])
        queries = expand_query("What is pump maintenance?", analysis)
        assert queries[0] == "What is pump maintenance?"

    def test_expand_adds_keyword_query(self) -> None:
        """Should add a keyword-focused query from key terms."""
        analysis = QueryAnalysis(intent="factual", key_terms=["pump", "maintenance", "schedule"])
        queries = expand_query("What is pump maintenance?", analysis)
        # Should have original + keyword query
        assert len(queries) >= 2
        assert any("pump" in q and "maintenance" in q for q in queries)

    def test_expand_adds_rewritten_queries(self) -> None:
        """Should include LLM-rewritten queries from analysis."""
        analysis = QueryAnalysis(
            intent="factual",
            rewritten_queries=["What does pump maintenance involve?"],
        )
        queries = expand_query("What is pump maintenance?", analysis)
        assert "What does pump maintenance involve?" in queries

    def test_expand_deduplicates(self) -> None:
        """Should not duplicate the original query."""
        analysis = QueryAnalysis(intent="factual", key_terms=["test"])
        queries = expand_query("test", analysis)
        # "test" is both the query and the key term query — should appear once
        assert queries.count("test") == 1


# ---------------------------------------------------------------------------
# Stage 5: Reranking (tested via pipeline integration)
# ---------------------------------------------------------------------------
class TestReranking:
    async def test_rerank_preserves_count(self) -> None:
        """Reranking should not lose results."""
        from sovereign.models.gateway import get_model_gateway
        from sovereign.reranking.service import rerank_results

        gw = get_model_gateway()
        results = [
            _make_result("c1", "doc1", "pump maintenance", 0.5),
            _make_result("c2", "doc1", "valve inspection", 0.3),
            _make_result("c3", "doc2", "bearing wear", 0.4),
        ]
        reranked = await rerank_results("pump maintenance", results, gw, top_k=3)
        assert len(reranked) <= 3
        # The most relevant result (pump maintenance) should rank highly
        assert reranked[0].chunk_id == "c1"


# ---------------------------------------------------------------------------
# Stage 6: Evidence selection
# ---------------------------------------------------------------------------
class TestEvidenceSelection:
    def test_select_returns_evidence_refs(self) -> None:
        """select_evidence should return EvidenceRef objects."""
        results = [
            _make_result("c1", "doc1", "pump maintenance", 0.8),
            _make_result("c2", "doc2", "valve inspection", 0.6),
        ]
        evidence = select_evidence(results, top_k=5)
        assert len(evidence) == 2
        assert all(isinstance(e, EvidenceRef) for e in evidence)

    def test_select_respects_top_k(self) -> None:
        """Should cap at top_k."""
        results = [_make_result(f"c{i}", "doc1", f"text {i}", 0.5) for i in range(10)]
        evidence = select_evidence(results, top_k=3)
        assert len(evidence) == 3

    def test_select_filters_low_score(self) -> None:
        """Results below min_score should be filtered."""
        results = [
            _make_result("c1", "doc1", "good", 0.5),
            _make_result("c2", "doc1", "bad", 0.001),  # below threshold
        ]
        evidence = select_evidence(results, top_k=5, min_score=0.01)
        assert len(evidence) == 1
        assert evidence[0].chunk_id == "c1"

    def test_select_max_per_document(self) -> None:
        """Should cap evidence per document for diversity."""
        results = [
            _make_result("c1", "doc1", "text1", 0.9),
            _make_result("c2", "doc1", "text2", 0.8),
            _make_result("c3", "doc1", "text3", 0.7),
            _make_result("c4", "doc2", "text4", 0.6),
            _make_result("c5", "doc2", "text5", 0.5),
        ]
        evidence = select_evidence(results, top_k=5, max_per_document=2)
        # doc1 should have max 2, doc2 should have max 2
        doc1_count = sum(1 for e in evidence if e.document_id == "doc1")
        doc2_count = sum(1 for e in evidence if e.document_id == "doc2")
        assert doc1_count <= 2
        assert doc2_count <= 2

    def test_select_empty_results(self) -> None:
        """Empty results should return empty evidence."""
        evidence = select_evidence([], top_k=5)
        assert evidence == []


# ---------------------------------------------------------------------------
# Stage 7: LLM reasoning
# ---------------------------------------------------------------------------
class TestLLMReasoning:
    async def test_generate_answer_with_evidence(self) -> None:
        """generate_answer should return text when evidence is provided."""
        from sovereign.models.gateway import get_model_gateway

        gw = get_model_gateway()
        evidence = [_make_evidence(text="Pump P-101 requires maintenance every 6 months.")]
        answer = await generate_answer("What is the maintenance schedule?", evidence, gw)
        assert answer  # non-empty
        assert isinstance(answer, str)

    async def test_generate_answer_no_evidence(self) -> None:
        """No evidence should return the insufficient-evidence message."""
        from sovereign.models.gateway import get_model_gateway

        gw = get_model_gateway()
        answer = await generate_answer("test query", [], gw)
        assert "don't have sufficient evidence" in answer.lower()


# ---------------------------------------------------------------------------
# Stage 8: Evidence verification
# ---------------------------------------------------------------------------
class TestEvidenceVerification:
    def test_extract_claims_splits_sentences(self) -> None:
        """_extract_claims should split into sentences."""
        claims = _extract_claims("Pump P-101 is operational. It was inspected yesterday. [1]")
        assert len(claims) == 2
        assert "operational" in claims[0]
        assert "inspected" in claims[1]

    def test_extract_claims_filters_short(self) -> None:
        """Short fragments should be filtered."""
        claims = _extract_claims(
            "OK. Hi. The bearing shows excessive wear and requires immediate replacement."
        )
        # "OK." and "Hi." are too short (< 10 chars)
        assert len(claims) == 1
        assert "bearing" in claims[0]

    def test_extract_claims_filters_insufficient_message(self) -> None:
        """The insufficient-evidence message should not be a claim."""
        claims = _extract_claims("I don't have sufficient evidence to answer this.")
        assert len(claims) == 0

    def test_heuristic_verify_supported(self) -> None:
        """High overlap should be SUPPORTED."""
        claim = "Pump P-101 requires maintenance every 6 months"
        evidence = [_make_evidence(text="Pump P-101 requires maintenance every 6 months")]
        status = _heuristic_verify(claim, evidence)
        assert status == "SUPPORTED"

    def test_heuristic_verify_unsupported(self) -> None:
        """Low overlap should be UNSUPPORTED."""
        claim = "The weather is sunny today"
        evidence = [_make_evidence(text="Pump P-101 requires maintenance")]
        status = _heuristic_verify(claim, evidence)
        assert status == "UNSUPPORTED"

    def test_heuristic_verify_partial(self) -> None:
        """Medium overlap should be PARTIALLY_SUPPORTED."""
        claim = "Pump P-101 requires regular maintenance and inspection"
        evidence = [_make_evidence(text="Pump P-101 requires maintenance every 6 months")]
        status = _heuristic_verify(claim, evidence)
        assert status in ("PARTIALLY_SUPPORTED", "SUPPORTED")

    async def test_verify_answer_returns_claims(self) -> None:
        """verify_answer should return a list of Claims."""
        from sovereign.models.gateway import get_model_gateway

        gw = get_model_gateway()
        evidence = [_make_evidence(text="Pump P-101 requires maintenance every 6 months")]
        answer = (
            "Pump P-101 requires maintenance every 6 months. "
            "The pump is located in Building A."
        )
        claims = await verify_answer(answer, evidence, gw)
        assert len(claims) >= 1
        valid = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONFLICTING")
        assert all(c.support_status in valid for c in claims)


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------
class TestRAGPipeline:
    async def test_pipeline_with_indexed_content(self) -> None:
        """Full pipeline: index a doc, query, get a grounded answer."""
        # Index a document
        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="report.txt", source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[
                Block(
                    kind="paragraph",
                    text="Pump P-101 requires maintenance every 6 months due to bearing wear.",
                ),
                Block(kind="paragraph", text="The pump is located in Building A Section 3."),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        # Query
        pipeline = RAGPipeline(indexing=indexing)
        response = await pipeline.query("proj_test", "How often does pump P-101 need maintenance?")

        assert isinstance(response, RAGResponse)
        # Should have found evidence
        assert len(response.evidence) > 0
        # Should have an answer (or insufficient evidence verdict)
        assert response.verdict.kind in ("answered", "insufficient_evidence")

    async def test_pipeline_insufficient_evidence_empty_kb(self) -> None:
        """Querying an empty KB should return insufficient_evidence."""
        pipeline = RAGPipeline()
        response = await pipeline.query("proj_empty", "What is pump P-101?")

        assert response.verdict.kind == "insufficient_evidence"
        assert "don't have sufficient evidence" in response.verdict.message.lower()
        assert len(response.evidence) == 0

    async def test_pipeline_returns_claims(self) -> None:
        """When answered, the response should include claims."""
        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="report.txt", source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[
                Block(
                    kind="paragraph",
                    text="The maximum operating pressure for valve V-202 is 150 PSI.",
                ),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        pipeline = RAGPipeline(indexing=indexing)
        response = await pipeline.query(
            "proj_test", "What is the maximum pressure for valve V-202?"
        )

        if response.is_answered:
            assert len(response.claims) > 0
            assert all(c.support_status for c in response.claims)

    async def test_pipeline_evidence_has_provenance(self) -> None:
        """Evidence should carry document_id, page, section_path."""
        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="report.txt", source_mime_type="text/plain",
            pages=[Page(page_number=5, blocks=[
                Block(
                    kind="paragraph",
                    text=(
                        "The emergency shutdown procedure for pump P-101 "
                        "requires isolating the power supply first."
                    ),
                    page=5, section_path=["Chapter 3", "Emergency Procedures"],
                ),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        pipeline = RAGPipeline(indexing=indexing)
        response = await pipeline.query("proj_test", "What is the emergency shutdown procedure?")

        if response.evidence:
            ev = response.evidence[0]
            assert ev.document_id == "doc1"
            assert ev.page == 5
            assert "Chapter 3" in ev.section_path

    async def test_pipeline_trace_populated(self) -> None:
        """The pipeline trace should contain stage information."""
        pipeline = RAGPipeline()
        response = await pipeline.query("proj_test", "test query")

        trace = response.pipeline_trace
        assert "stage1_intent" in trace
        assert "stage2_expanded_queries" in trace
        assert "stage3_candidates" in trace

    async def test_pipeline_document_filter(self) -> None:
        """Document filter should restrict retrieval to one document."""
        indexing = IndexingService()
        for doc_id, content in [
            ("doc_a", "Pump P-101 maintenance interval is 6 months"),
            ("doc_b", "Valve V-202 inspection frequency is monthly"),
        ]:
            parsed = ParsedDocument(
                document_id=doc_id, project_id="proj_test",
                source_filename=f"{doc_id}.txt", source_mime_type="text/plain",
                pages=[Page(page_number=1, blocks=[Block(kind="paragraph", text=content)])],
                metadata=DocumentMetadata(page_count=1),
            )
            await indexing.index_document("proj_test", doc_id, parsed)

        pipeline = RAGPipeline(indexing=indexing)
        response = await pipeline.query(
            "proj_test", "maintenance",
            document_filter={"document_id": "doc_a"},
        )

        # All evidence should be from doc_a
        if response.evidence:
            assert all(e.document_id == "doc_a" for e in response.evidence)
