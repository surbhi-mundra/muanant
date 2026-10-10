"""Tests for sovereign.vision.workflows — diagram extraction, claims, drawing analysis."""

from __future__ import annotations

import pytest

from sovereign.models.gateway import reset_model_gateway
from sovereign.parsing.model import (
    Block,
    BoundingBox,
    DocumentMetadata,
    Figure,
    Page,
    ParsedDocument,
)
from sovereign.vision.workflows import (
    DiagramDescription,
    DiagramExtractor,
    DrawingAnalyzer,
    ImageGroundedClaimer,
    _classify_diagram_type,
    _classify_drawing_type,
    _extract_components,
    run_vision_workflow,
)


@pytest.fixture(autouse=True)
def _reset_gateway():
    reset_model_gateway()
    yield
    reset_model_gateway()


def _make_parsed_with_figures(figures: list[Figure]) -> ParsedDocument:
    """Build a ParsedDocument with figure blocks."""
    blocks = [
        Block(kind="figure", figure=fig, page=fig.page)
        for fig in figures
    ]
    return ParsedDocument(
        document_id="doc_test",
        project_id="proj_test",
        source_filename="test.pdf",
        source_mime_type="application/pdf",
        pages=[Page(page_number=1, blocks=blocks)],
        metadata=DocumentMetadata(page_count=1),
    )


class TestDiagramExtractor:
    async def test_extract_no_figures(self) -> None:
        """A document with no figures should return empty list."""
        parsed = ParsedDocument(
            document_id="doc1",
            source_filename="test.txt",
            source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[])],
            metadata=DocumentMetadata(page_count=1),
        )
        extractor = DiagramExtractor()
        results = await extractor.extract_from_document(parsed)
        assert results == []

    async def test_extract_with_caption_only(self) -> None:
        """Figures without image data should use caption."""
        fig = Figure(caption="Pump P-101 layout diagram", page=1)
        parsed = _make_parsed_with_figures([fig])
        extractor = DiagramExtractor()
        results = await extractor.extract_from_document(parsed, document_data=None)
        assert len(results) == 1
        assert "Pump P-101" in results[0].description
        assert results[0].caption == "Pump P-101 layout diagram"

    async def test_extract_multiple_figures(self) -> None:
        """Multiple figures should all be described."""
        figs = [
            Figure(caption="Figure 1: P&ID", page=1),
            Figure(caption="Figure 2: Electrical schematic", page=2),
            Figure(caption="Figure 3: Photo of equipment", page=3),
        ]
        parsed = _make_parsed_with_figures(figs)
        extractor = DiagramExtractor()
        results = await extractor.extract_from_document(parsed)
        assert len(results) == 3
        assert results[0].figure_index == 0
        assert results[1].figure_index == 1
        assert results[2].figure_index == 2


class TestDrawingAnalyzer:
    async def test_analyze_auto_detect(self) -> None:
        """DrawingAnalyzer should work with auto-detection."""
        analyzer = DrawingAnalyzer()
        # Use a tiny PNG
        import io

        from PIL import Image

        img = Image.new("RGB", (100, 100), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = await analyzer.analyze(buf.getvalue(), drawing_type="auto")
        assert isinstance(result, DiagramDescription)
        assert result.description  # non-empty

    async def test_analyze_specific_type(self) -> None:
        """Should accept a specific drawing type."""
        analyzer = DrawingAnalyzer()
        import io

        from PIL import Image

        img = Image.new("RGB", (100, 100), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = await analyzer.analyze(buf.getvalue(), drawing_type="pid")
        assert result.diagram_type == "pid"


class TestImageGroundedClaimer:
    def test_extract_claims_from_descriptions(self) -> None:
        """Should extract claims from diagram descriptions."""
        descriptions = [
            DiagramDescription(
                figure_index=0,
                caption="P&ID",
                description="The diagram shows pump P-101 connected to valve V-202. "
                           "The pump has a capacity of 500 GPM. "
                           "Pressure gauge PI-301 is installed on the discharge line.",
            ),
        ]
        claimer = ImageGroundedClaimer()
        claims = claimer.extract_claims(descriptions)
        assert len(claims) >= 2  # at least 2 factual sentences
        assert all(c.support_status == "SUPPORTED" for c in claims)
        assert all(c.source_figure_index == 0 for c in claims)

    def test_extract_skips_questions(self) -> None:
        """Questions should not become claims."""
        descriptions = [
            DiagramDescription(
                figure_index=0,
                caption=None,
                description="Is this the main pump? What is the flow rate?",
            ),
        ]
        claimer = ImageGroundedClaimer()
        claims = claimer.extract_claims(descriptions)
        assert len(claims) == 0

    def test_extract_skips_instruction_text(self) -> None:
        """Instruction-like text should not become claims."""
        descriptions = [
            DiagramDescription(
                figure_index=0,
                caption=None,
                description="Identify all equipment. List the components. Be precise.",
            ),
        ]
        claimer = ImageGroundedClaimer()
        claims = claimer.extract_claims(descriptions)
        assert len(claims) == 0

    def test_extract_empty_descriptions(self) -> None:
        """Empty descriptions should return no claims."""
        claimer = ImageGroundedClaimer()
        claims = claimer.extract_claims([])
        assert claims == []


class TestClassificationHelpers:
    def test_classify_diagram_type_pid(self) -> None:
        assert _classify_diagram_type("P&ID showing piping and valves") == "pid"

    def test_classify_diagram_type_electrical(self) -> None:
        assert _classify_diagram_type("electrical schematic with breakers") == "electrical"

    def test_classify_diagram_type_mechanical(self) -> None:
        assert _classify_diagram_type("mechanical drawing with dimensions") == "mechanical"

    def test_classify_diagram_type_flowchart(self) -> None:
        assert _classify_diagram_type("process flow chart") == "flowchart"

    def test_classify_diagram_type_photo(self) -> None:
        assert _classify_diagram_type("inspection photograph") == "photo"

    def test_classify_diagram_type_unknown(self) -> None:
        assert _classify_diagram_type("random text") == "unknown"

    def test_classify_drawing_type_from_text(self) -> None:
        assert _classify_drawing_type("this is a pid") == "pid"
        assert _classify_drawing_type("ELECTRICAL") == "electrical"
        assert _classify_drawing_type("something else") == "photo"

    def test_extract_components_tags(self) -> None:
        """Should extract tag-like component identifiers."""
        text = "Pump P-101 and valve V-202 are connected. Sensor FT-301 monitors flow."
        components = _extract_components(text)
        assert "P-101" in components
        assert "V-202" in components
        assert "FT-301" in components


class TestVisionWorkflow:
    async def test_run_vision_workflow_no_figures(self) -> None:
        """Document with no figures should return empty results."""
        parsed = ParsedDocument(
            document_id="doc1",
            source_filename="test.txt",
            source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[])],
            metadata=DocumentMetadata(page_count=1),
        )
        result = await run_vision_workflow(parsed)
        assert result.diagram_descriptions == []
        assert result.image_grounded_claims == []
        assert "No figures" in result.summary

    async def test_run_vision_workflow_with_figures(self) -> None:
        """Document with figures should produce descriptions + claims."""
        fig = Figure(
            caption="P&ID for pump system",
            page=1,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
        )
        parsed = _make_parsed_with_figures([fig])
        result = await run_vision_workflow(parsed)
        assert len(result.diagram_descriptions) == 1
        assert result.summary
        assert "1 figure" in result.summary or "1 figure(s)" in result.summary

    async def test_run_vision_workflow_errors_caught(self) -> None:
        """Errors should be caught and added to result.errors."""
        # Pass a parsed doc that will cause an error
        parsed = ParsedDocument(
            document_id="doc1",
            source_filename="test.pdf",
            source_mime_type="application/pdf",
            pages=[],
            metadata=DocumentMetadata(page_count=0),
        )
        result = await run_vision_workflow(parsed)
        # No crash, just empty results
        assert isinstance(result.diagram_descriptions, list)
