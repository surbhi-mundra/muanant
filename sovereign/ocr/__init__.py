"""OCR pipeline — pluggable engine via the OCR protocol.

Phase 3 delivers:
- Tesseract adapter (real, CPU-friendly — binary already installed)
- Scanned-PDF detection (render page → check text density)
- OCR pipeline that merges OCR results into a ParsedDocument
- Image OCR for standalone image uploads (PNG/JPG/WEBP)

The OCR protocol interface was defined in Phase 1
(``sovereign.models.schemas.OCR``). The Tesseract adapter satisfies it.
Future adapters (Surya, PaddleOCR) register in
``sovereign.models.backends`` and are selected via ``configs/models.yaml``.
"""
