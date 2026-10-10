"""Vision workflows — diagram extraction, image-grounded claims, drawing analysis.

Phase 8 extends the Phase 3 vision service with higher-level workflows:

- ``DiagramExtractor``: extracts figures/diagrams from ParsedDocuments,
  renders them to images, and describes them via the VisionLLM.
- ``ImageGroundedClaimer``: generates claims grounded in image descriptions
  (e.g. "the diagram shows pump P-101 with a bypass valve").
- ``DrawingAnalyzer``: specialized analysis for engineering drawings
  (P&IDs, electrical schematics, mechanical layouts) with domain-specific
  prompts.

These workflows integrate with the agent system (Phase 7) — the Vision
agent uses them when processing image-containing documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway, get_model_gateway
from sovereign.parsing.model import Figure, ParsedDocument
from sovereign.vision.service import VisionService

log = get_logger(__name__)


@dataclass(slots=True)
class DiagramDescription:
    """Result of describing a single diagram/figure."""

    figure_index: int
    caption: str | None
    description: str
    diagram_type: str = "unknown"  # pid, electrical, mechanical, flowchart, photo, unknown
    components_detected: list[str] = field(default_factory=list)
    text_extracted: str = ""


@dataclass(slots=True)
class ImageGroundedClaim:
    """A claim grounded in an image description."""

    text: str
    source_figure_index: int
    support_status: str = "SUPPORTED"  # from image evidence


@dataclass(slots=True)
class VisionWorkflowResult:
    """Complete output of a vision workflow run on a document."""

    document_id: str
    diagram_descriptions: list[DiagramDescription] = field(default_factory=list)
    image_grounded_claims: list[ImageGroundedClaim] = field(default_factory=list)
    summary: str = ""
    errors: list[str] = field(default_factory=list)


class DiagramExtractor:
    """Extracts and describes figures/diagrams from a ParsedDocument.

    For PDF documents, figures are rendered to images via PyMuPDF.
    For other formats, figure descriptions come from the parsed structure.
    """

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    async def extract_from_document(
        self,
        parsed: ParsedDocument,
        document_data: bytes | None = None,
    ) -> list[DiagramDescription]:
        """Extract and describe all figures from a parsed document.

        Args:
            parsed: the ParsedDocument with figure blocks.
            document_data: raw document bytes (for rendering PDF figures).
                         If None, only captions are used.
        """
        figures = parsed.figures
        if not figures:
            return []

        vision = VisionService(self._gateway)
        results: list[DiagramDescription] = []

        for i, fig in enumerate(figures):
            try:
                desc = await self._describe_figure(
                    fig, i, vision, document_data, parsed.source_mime_type
                )
                results.append(desc)
            except Exception as e:
                log.error("vision.diagram.extract_failed", figure_index=i, error=str(e))
                results.append(
                    DiagramDescription(
                        figure_index=i,
                        caption=fig.caption,
                        description=f"[extraction failed: {e}]",
                    )
                )

        log.info(
            "vision.diagram.extracted",
            document_id=parsed.document_id,
            figure_count=len(results),
        )
        return results

    async def _describe_figure(
        self,
        fig: Figure,
        index: int,
        vision: VisionService,
        document_data: bytes | None,
        mime_type: str,
    ) -> DiagramDescription:
        """Describe a single figure."""
        caption = fig.caption

        # If we have document data and it's a PDF, try to render the figure
        image_data: bytes | None = None
        if document_data and mime_type == "application/pdf" and fig.page and fig.bbox:
            image_data = _render_pdf_region(
                document_data, fig.page, fig.bbox.x0, fig.bbox.y0,
                fig.bbox.x1, fig.bbox.y1,
            )

        if image_data:
            # Use the vision model to describe the rendered image
            result = await vision.describe_diagram(image_data, "image/png")
            description = result.text
            diagram_type = _classify_diagram_type(description, caption)
            components = _extract_components(description)
            text_extracted = _extract_text_from_description(description)
        else:
            # No image data — use caption only
            description = f"[Figure {index + 1}] {caption or 'No caption available'}"
            diagram_type = "unknown"
            components = []
            text_extracted = caption or ""

        return DiagramDescription(
            figure_index=index,
            caption=caption,
            description=description,
            diagram_type=diagram_type,
            components_detected=components,
            text_extracted=text_extracted,
        )


class DrawingAnalyzer:
    """Specialized analysis for engineering drawings.

    Provides domain-specific prompts for:
    - P&IDs (Piping & Instrumentation Diagrams)
    - Electrical schematics
    - Mechanical layouts
    - Flow charts / process diagrams
    """

    _PROMPTS: dict[str, str] = {
        "pid": (
            "This is a Piping & Instrumentation Diagram (P&ID). Identify:\n"
            "1. All equipment (pumps, vessels, heat exchangers, valves)\n"
            "2. All instruments (sensors, transmitters, controllers) with tag numbers\n"
            "3. Pipe sizes and line numbers if visible\n"
            "4. Control loops and interlocks\n"
            "5. Safety devices (relief valves, PSVs, alarms)\n"
            "List each item with its tag number."
        ),
        "electrical": (
            "This is an electrical schematic. Identify:\n"
            "1. Power sources (generators, transformers, batteries)\n"
            "2. Protection devices (breakers, fuses, relays)\n"
            "3. Loads (motors, heaters, lights)\n"
            "4. Control circuits and logic\n"
            "5. Wire/connection numbers if visible\n"
            "List each component with its reference designator."
        ),
        "mechanical": (
            "This is a mechanical drawing/layout. Identify:\n"
            "1. Equipment and their positions\n"
            "2. Dimensions and tolerances if shown\n"
            "3. Materials and specifications\n"
            "4. Assembly details\n"
            "5. Any annotations or callouts\n"
            "Be precise about measurements."
        ),
        "flowchart": (
            "This is a process flow diagram or flowchart. Identify:\n"
            "1. All process steps/operations\n"
            "2. Decision points and branches\n"
            "3. Flow direction and sequence\n"
            "4. Inputs and outputs\n"
            "5. Any loops or feedback paths\n"
            "List the steps in order."
        ),
        "photo": (
            "This is an industrial photograph. Describe:\n"
            "1. The equipment or facility shown\n"
            "2. Visible condition (new, aged, damaged)\n"
            "3. Any visible defects or anomalies\n"
            "4. Labels, tags, or markings\n"
            "5. Environmental context (indoor/outdoor, operating/shutdown)\n"
            "Be objective and specific."
        ),
    }

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    async def analyze(
        self,
        image_data: bytes,
        drawing_type: str = "auto",
    ) -> DiagramDescription:
        """Analyze an engineering drawing with a specialized prompt.

        Args:
            image_data: the drawing image bytes.
            drawing_type: one of 'pid', 'electrical', 'mechanical',
                         'flowchart', 'photo', or 'auto' (auto-detect).
        """
        vision = VisionService(self._gateway)

        # Auto-detect type if requested
        if drawing_type == "auto":
            general_result = await vision.describe_image(
                image_data, "image/png",
                "What type of technical drawing or image is this? "
                "Respond with one word: pid, electrical, mechanical, flowchart, or photo."
            )
            drawing_type = _classify_drawing_type(general_result.text)

        prompt = self._PROMPTS.get(drawing_type, self._PROMPTS["photo"])
        result = await vision.describe_image(image_data, "image/png", prompt)

        return DiagramDescription(
            figure_index=0,
            caption=None,
            description=result.text,
            diagram_type=drawing_type,
            components_detected=_extract_components(result.text),
            text_extracted=_extract_text_from_description(result.text),
        )


class ImageGroundedClaimer:
    """Generates claims grounded in image/diagram descriptions.

    Takes DiagramDescriptions and extracts factual claims that are
    supported by the visual evidence.
    """

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    def extract_claims(
        self, descriptions: list[DiagramDescription]
    ) -> list[ImageGroundedClaim]:
        """Extract image-grounded claims from diagram descriptions.

        Uses heuristic extraction: each sentence in the description that
        contains a factual statement becomes a claim. In prod, the LLM
        does proper claim extraction.
        """
        claims: list[ImageGroundedClaim] = []

        for desc in descriptions:
            if not desc.description or desc.description.startswith("["):
                continue

            # Split into sentences
            import re

            sentences = re.split(r"(?<=[.!?])\s+", desc.description)

            for sent in sentences:
                sent = sent.strip()
                # Skip short fragments and non-claim text
                if len(sent) < 15:
                    continue
                # Skip questions
                if sent.endswith("?"):
                    continue
                # Skip instruction-like text
                if sent.startswith(("Identify", "List", "Describe", "Be ")):
                    continue

                claims.append(
                    ImageGroundedClaim(
                        text=sent,
                        source_figure_index=desc.figure_index,
                        support_status="SUPPORTED",
                    )
                )

        log.info("vision.claims.extracted", count=len(claims))
        return claims


# ---------------------------------------------------------------------------
# Full vision workflow
# ---------------------------------------------------------------------------
async def run_vision_workflow(
    parsed: ParsedDocument,
    document_data: bytes | None = None,
    gateway: ModelGateway | None = None,
) -> VisionWorkflowResult:
    """Run the full vision workflow on a document.

    1. Extract and describe all diagrams/figures.
    2. Generate image-grounded claims from descriptions.
    3. Produce a summary.
    """
    result = VisionWorkflowResult(document_id=parsed.document_id or "")

    try:
        # 1. Extract diagrams
        extractor = DiagramExtractor(gateway)
        descriptions = await extractor.extract_from_document(parsed, document_data)
        result.diagram_descriptions = descriptions

        # 2. Extract claims
        claimer = ImageGroundedClaimer(gateway)
        claims = claimer.extract_claims(descriptions)
        result.image_grounded_claims = claims

        # 3. Summary
        if descriptions:
            parts = [f"{len(descriptions)} figure(s) analyzed."]
            type_counts: dict[str, int] = {}
            for d in descriptions:
                type_counts[d.diagram_type] = type_counts.get(d.diagram_type, 0) + 1
            type_str = ", ".join(f"{count} {dtype}" for dtype, count in type_counts.items())
            parts.append(f"Types: {type_str}.")
            parts.append(f"{len(claims)} image-grounded claims extracted.")
            result.summary = " ".join(parts)
        else:
            result.summary = "No figures found in document."

    except Exception as e:
        log.error("vision.workflow.failed", error=str(e))
        result.errors.append(str(e))

    log.info(
        "vision.workflow.complete",
        document_id=parsed.document_id,
        diagrams=len(result.diagram_descriptions),
        claims=len(result.image_grounded_claims),
    )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _render_pdf_region(
    pdf_data: bytes,
    page_num: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> bytes | None:
    """Render a region of a PDF page to PNG."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_data, filetype="pdf")
        if page_num < 1 or page_num > len(doc):
            return None
        page = doc[page_num - 1]
        clip = fitz.Rect(x0, y0, x1, y1)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
        png: bytes = pix.tobytes("png")
        doc.close()
        return png
    except Exception as e:
        log.error("vision.render_region.failed", page=page_num, error=str(e))
        return None


def _classify_diagram_type(description: str, caption: str | None = None) -> str:
    """Classify the type of diagram from its description + caption."""
    text = (description + " " + (caption or "")).lower()

    if any(w in text for w in ("p&id", "piping", "instrumentation", "valve", "pipe")):
        return "pid"
    if any(w in text for w in ("electrical", "schematic", "circuit", "breaker", "wiring")):
        return "electrical"
    if any(w in text for w in ("mechanical", "dimension", "tolerance", "assembly")):
        return "mechanical"
    if any(w in text for w in ("flowchart", "flow chart", "process flow", "decision")):
        return "flowchart"
    if any(w in text for w in ("photo", "photograph", "image", "inspection")):
        return "photo"
    return "unknown"


def _classify_drawing_type(text: str) -> str:
    """Classify drawing type from a one-word response."""
    text_lower = text.lower().strip()
    for dtype in ("pid", "electrical", "mechanical", "flowchart", "photo"):
        if dtype in text_lower:
            return dtype
    return "photo"


def _extract_components(description: str) -> list[str]:
    """Extract component names from a description (heuristic)."""
    import re

    # Look for tag-like patterns: P-101, V-202, FT-301, etc.
    tag_pattern = re.compile(r"\b([A-Z]{1,3})-(\d{3,4})\b")
    tags = tag_pattern.findall(description)
    return [f"{prefix}-{num}" for prefix, num in tags]


def _extract_text_from_description(description: str) -> str:
    """Extract visible text mentioned in the description."""
    # The description already contains the text — return as-is for now.
    # In prod, a more sophisticated extraction would separate quoted text.
    return description
