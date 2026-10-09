"""Ingestion service — secure upload, validation, quarantine, parsing.

This is the entry point for all document uploads. The flow:

1. **Validate** — check MIME type (from magic bytes, not client header),
   size, and file integrity (qpdf for PDFs).
2. **Quarantine** — if validation fails, move to quarantine for admin
   review. Never auto-reject; the admin decides.
3. **Dedup** — compute SHA-256; if the same content already exists in
   the project, return the existing document.
4. **Store** — write the raw bytes to the object store under an opaque
   UUID key (never the user-supplied filename).
5. **Persist** — create a Document row with status="stored".
6. **Parse** — run the structure-preserving parser, store the
   ParsedDocument JSON alongside the raw bytes.
7. **Audit** — write an audit event for every step.

The parse step is Phase 2's terminal point. Phase 4 (Knowledge base)
will add chunking + embedding + indexing on top of the ParsedDocument.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sovereign.audit.chain import AuditEventPayload
from sovereign.audit.log import write_event
from sovereign.core.errors import (
    NotFoundError,
)
from sovereign.core.ids import new_ulid, utcnow
from sovereign.core.logging import get_logger
from sovereign.parsing.model import ParsedDocument
from sovereign.parsing.registry import parse_document, supported_mimes
from sovereign.storage.db.base import session_scope
from sovereign.storage.db.models import Document
from sovereign.storage.objects import (
    ObjectStore,
    get_object_store,
    new_storage_key,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# MIME detection from magic bytes
# ---------------------------------------------------------------------------
_MAGIC_BYTES: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"\x50\x4b\x03\x04", "application/zip"),  # DOCX/XLSX are ZIP
    (b"\xd0\xcf\x11\xe0", "application/msoffice"),  # OLE2 (old Office)
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),  # WEBP starts with RIFF....WEBP
]


def _detect_mime(data: bytes, filename: str, client_mime: str) -> str:
    """Detect the true MIME type from magic bytes + filename.

    NEVER trusts the client-supplied ``Content-Type`` header alone.
    """
    # 1. Magic bytes
    for magic, mime in _MAGIC_BYTES:
        if data[:len(magic)] == magic:
            # DOCX vs XLSX are both ZIP — check internal structure
            if mime == "application/zip":
                if _is_docx(data):
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if _is_xlsx(data):
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                return mime
            # WEBP: RIFF....WEBP — verify the WEBP marker
            if mime == "image/webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                continue  # RIFF but not WEBP — keep checking
            return mime

    # 2. Text detection
    try:
        data.decode("utf-8")
        # Check for markdown indicators
        if filename.endswith(".md") or filename.endswith(".markdown"):
            return "text/markdown"
        if filename.endswith(".csv"):
            return "text/csv"
        return "text/plain"
    except UnicodeDecodeError:
        pass

    # 3. Fall back to client-provided MIME (with warning)
    log.warning(
        "ingestion.mime.fallback",
        filename=filename,
        client_mime=client_mime,
    )
    return client_mime or "application/octet-stream"


def _is_docx(data: bytes) -> bool:
    """Check if ZIP data contains word/ (DOCX signature)."""
    return b"word/" in data[:2048]


def _is_xlsx(data: bytes) -> bool:
    """Check if ZIP data contains xl/ (XLSX signature)."""
    return b"xl/" in data[:2048]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    is_valid: bool
    mime_type: str
    sha256: str
    size_bytes: int
    warnings: list[str] = field(default_factory=list)
    quarantine_reason: str | None = None


def validate_document(
    data: bytes,
    filename: str,
    client_mime: str,
    *,
    max_size_mb: int = 200,
) -> ValidationResult:
    """Validate an uploaded document.

    Returns a ValidationResult with the detected MIME type and SHA-256.
    If validation fails, ``is_valid`` is False and ``quarantine_reason``
    explains why.
    """
    warnings: list[str] = []

    # Size check
    size = len(data)
    if size == 0:
        return ValidationResult(
            is_valid=False,
            mime_type="",
            sha256="",
            size_bytes=0,
            quarantine_reason="empty file",
        )
    if size > max_size_mb * 1024 * 1024:
        return ValidationResult(
            is_valid=False,
            mime_type="",
            sha256="",
            size_bytes=size,
            quarantine_reason=f"file exceeds {max_size_mb}MB limit",
        )

    # MIME detection
    mime = _detect_mime(data, filename, client_mime)

    # Check if MIME is supported
    supported = supported_mimes()
    if mime not in supported and mime not in ("application/zip", "application/octet-stream"):
        # For unsupported types, still accept but warn — the parser will
        # reject with a clear error.
        warnings.append(f"unsupported MIME type: {mime}")

    # SHA-256
    sha256 = hashlib.sha256(data).hexdigest()

    # PDF integrity check (if qpdf is available)
    if mime == "application/pdf":
        qpdf_warning = _check_pdf_integrity(data)
        if qpdf_warning:
            warnings.append(qpdf_warning)

    return ValidationResult(
        is_valid=True,
        mime_type=mime,
        sha256=sha256,
        size_bytes=size,
        warnings=warnings,
    )


def _check_pdf_integrity(data: bytes) -> str | None:
    """Run qpdf --check on the PDF if available. Returns warning or None."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    qpdf = shutil.which("qpdf")
    if not qpdf:
        return None  # qpdf not installed — skip

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            f.flush()
            result = subprocess.run(  # noqa: S603 — qpdf is a known binary
                [qpdf, "--check", f.name],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,  # qpdf returns non-zero on warnings, not just errors
            )
            Path(f.name).unlink(missing_ok=True)
        if result.returncode != 0:
            return f"qpdf check warning: {result.stderr[:200]}"
    except Exception as e:
        return f"qpdf check failed: {e}"

    return None


# ---------------------------------------------------------------------------
# Ingestion service
# ---------------------------------------------------------------------------
@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    document_id: str
    project_id: str
    status: str  # "stored" | "parsed" | "quarantined" | "duplicate"
    mime_type: str
    sha256: str
    size_bytes: int
    version: int
    parse_warnings: list[str] = field(default_factory=list)
    is_duplicate: bool = False
    quarantine_reason: str | None = None


async def ingest_document(
    project_id: str,
    filename: str,
    data: bytes,
    client_mime: str = "",
    *,
    store: ObjectStore | None = None,
    max_size_mb: int = 200,
) -> IngestResult:
    """Ingest a document: validate → store → parse → persist.

    This is the main entry point for document upload. Returns an
    ``IngestResult`` with the document ID and status.
    """
    if store is None:
        store = get_object_store()

    # 1. Validate
    validation = validate_document(data, filename, client_mime, max_size_mb=max_size_mb)

    if not validation.is_valid:
        # Quarantine: store the file for admin review, return quarantine status
        quarantine_key = new_storage_key()
        store.put(project_id, quarantine_key, data)
        _audit_ingest(
            project_id=project_id,
            action="document.quarantine",
            outcome="blocked",
            filename=filename,
            reason=validation.quarantine_reason or "unknown",
            size=validation.size_bytes,
        )
        return IngestResult(
            document_id="",
            project_id=project_id,
            status="quarantined",
            mime_type=validation.mime_type,
            sha256=validation.sha256,
            size_bytes=validation.size_bytes,
            version=0,
            quarantine_reason=validation.quarantine_reason,
        )

    # 2. Dedup check
    with session_scope() as s:
        existing = (
            s.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.sha256 == validation.sha256,
            )
            .first()
        )

    if existing:
        _audit_ingest(
            project_id=project_id,
            action="document.duplicate",
            outcome="success",
            filename=filename,
            sha256=validation.sha256,
            existing_doc_id=existing.id,
        )
        return IngestResult(
            document_id=existing.id,
            project_id=project_id,
            status="duplicate",
            mime_type=existing.mime_type,
            sha256=validation.sha256,
            size_bytes=validation.size_bytes,
            version=existing.version,
            is_duplicate=True,
        )

    # 3. Store raw bytes
    storage_key = new_storage_key()
    store.put(project_id, storage_key, data)

    # 4. Parse (or OCR for scanned PDFs / images)
    doc_id = new_ulid()
    parse_warnings: list[str] = list(validation.warnings)
    parsed: ParsedDocument | None = None

    # Handle image MIME types → OCR pipeline
    if validation.mime_type.startswith("image/"):
        try:
            from sovereign.ocr.pipeline import OCROptions, ocr_image

            parsed = await ocr_image(
                image_data=data,
                filename=filename,
                media_type=validation.mime_type,
                options=OCROptions(),
            )
            parsed.document_id = doc_id
            parsed.project_id = project_id
            parsed.source_sha256 = validation.sha256
            parse_warnings.extend(parsed.parse_warnings)
        except Exception as e:
            log.error(
                "ingestion.ocr_image.failed",
                document_id=doc_id, filename=filename, error=str(e),
            )
            parse_warnings.append(f"image OCR failed: {e}")
    # Handle scanned PDFs → detect + OCR if needed
    elif validation.mime_type == "application/pdf":
        try:
            from sovereign.ocr.pipeline import detect_scanned_pdf

            scan_report = detect_scanned_pdf(data)
            if scan_report.any_scanned:
                log.info(
                    "ingestion.scanned_pdf_detected",
                    filename=filename,
                    scanned_pages=len(scan_report.scanned_page_numbers),
                    total_pages=scan_report.total_pages,
                )
                from sovereign.ocr.pipeline import OCROptions, ocr_pdf

                parsed = await ocr_pdf(
                    pdf_data=data,
                    filename=filename,
                    options=OCROptions(),
                )
                parsed.document_id = doc_id
                parsed.project_id = project_id
                parsed.source_sha256 = validation.sha256
                parse_warnings.extend(parsed.parse_warnings)
                parse_warnings.append(
                    f"OCR applied to {len(scan_report.scanned_page_numbers)} "
                    f"of {scan_report.total_pages} pages"
                )
            else:
                # Normal PDF with extractable text
                parsed = parse_document(data, filename, validation.mime_type)
                parsed.document_id = doc_id
                parsed.project_id = project_id
                parsed.source_sha256 = validation.sha256
                parse_warnings.extend(parsed.parse_warnings)
        except Exception as e:
            log.error(
                "ingestion.pdf_ocr.failed",
                document_id=doc_id,
                filename=filename,
                error=str(e),
            )
            # Fallback to normal parsing
            try:
                parsed = parse_document(data, filename, validation.mime_type)
                parsed.document_id = doc_id
                parsed.project_id = project_id
                parsed.source_sha256 = validation.sha256
                parse_warnings.extend(parsed.parse_warnings)
            except Exception as e2:
                log.error(
                    "ingestion.parse.failed",
                    document_id=doc_id, filename=filename, error=str(e2),
                )
                parse_warnings.append(f"parse failed: {e2}")
    else:
        # All other formats: standard parsing
        try:
            parsed = parse_document(data, filename, validation.mime_type)
            parsed.document_id = doc_id
            parsed.project_id = project_id
            parsed.source_sha256 = validation.sha256
            parse_warnings.extend(parsed.parse_warnings)
        except Exception as e:
            log.error(
                "ingestion.parse.failed",
                document_id=doc_id,
                filename=filename,
                error=str(e),
            )
            parse_warnings.append(f"parse failed: {e}")

    # 5. Persist Document row
    version = _get_next_version(project_id, filename)
    doc = Document(
        id=doc_id,
        project_id=project_id,
        original_filename=filename,
        storage_key=storage_key,
        mime_type=validation.mime_type,
        size_bytes=validation.size_bytes,
        sha256=validation.sha256,
        status="parsed" if parsed else "stored",
        version=version,
        metadata_json=json.dumps(
            {
                "parse_warnings": parse_warnings,
                "parsed_at": utcnow().isoformat(),
                "word_count": parsed.metadata.word_count if parsed else 0,
                "page_count": parsed.metadata.page_count if parsed else 0,
            }
        ),
    )

    with session_scope() as s:
        s.add(doc)
        # Write audit event in the same transaction
        write_event(
            s,
            AuditEventPayload(
                project_id=project_id,
                category="ingestion",
                action="document.ingest",
                outcome="success",
                details={
                    "document_id": doc_id,
                    "filename": filename,
                    "mime_type": validation.mime_type,
                    "size_bytes": validation.size_bytes,
                    "version": version,
                    "status": doc.status,
                    "parse_warnings": parse_warnings[:5],  # cap for audit
                },
            ),
        )

    # 6. Store parsed document JSON (if parse succeeded)
    if parsed:
        parsed_key = f"{storage_key}.parsed.json"
        store.put(project_id, parsed_key, parsed.model_dump_json().encode("utf-8"))

    log.info(
        "ingestion.complete",
        document_id=doc_id,
        project_id=project_id,
        filename=filename,
        status=doc.status,
        size=validation.size_bytes,
    )

    return IngestResult(
        document_id=doc_id,
        project_id=project_id,
        status=doc.status,
        mime_type=validation.mime_type,
        sha256=validation.sha256,
        size_bytes=validation.size_bytes,
        version=version,
        parse_warnings=parse_warnings,
    )


def get_document(project_id: str, document_id: str) -> Document:
    """Retrieve a document by ID. Raises NotFoundError if missing or wrong project."""
    with session_scope() as s:
        doc = (
            s.query(Document)
            .filter(
                Document.id == document_id,
                Document.project_id == project_id,
            )
            .first()
        )
        if doc is None:
            msg = f"document not found: {document_id}"
            raise NotFoundError(msg)
        # Detach from session
        s.expunge(doc)
        return doc


def get_parsed_document(
    project_id: str, document_id: str, store: ObjectStore | None = None
) -> ParsedDocument:
    """Retrieve the parsed document JSON from the object store."""
    if store is None:
        store = get_object_store()

    doc = get_document(project_id, document_id)
    parsed_key = f"{doc.storage_key}.parsed.json"
    try:
        data = store.get(project_id, parsed_key)
    except NotFoundError:
        msg = f"parsed document not found for {document_id}"
        raise NotFoundError(msg) from None

    return ParsedDocument.model_validate_json(data)


def list_documents(project_id: str, limit: int = 100, offset: int = 0) -> list[Document]:
    """List documents in a project."""
    with session_scope() as s:
        docs = (
            s.query(Document)
            .filter(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        for d in docs:
            s.expunge(d)
        return docs


def delete_document(project_id: str, document_id: str) -> None:
    """Delete a document: remove from DB + object store."""
    store = get_object_store()

    with session_scope() as s:
        doc = (
            s.query(Document)
            .filter(
                Document.id == document_id,
                Document.project_id == project_id,
            )
            .first()
        )
        if doc is None:
            msg = f"document not found: {document_id}"
            raise NotFoundError(msg)

        storage_key = doc.storage_key
        s.delete(doc)

        write_event(
            s,
            AuditEventPayload(
                project_id=project_id,
                category="ingestion",
                action="document.delete",
                outcome="success",
                details={"document_id": document_id, "filename": doc.original_filename},
            ),
        )

    # Delete from object store (after DB commit)
    store.delete(project_id, storage_key)
    store.delete(project_id, f"{storage_key}.parsed.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_next_version(project_id: str, filename: str) -> int:
    """Get the next version number for a filename in a project."""
    with session_scope() as s:
        max_version = (
            s.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.original_filename == filename,
            )
            .order_by(Document.version.desc())
            .first()
        )
        return (max_version.version + 1) if max_version else 1


def _audit_ingest(
    project_id: str,
    action: str,
    outcome: str,
    **details: object,
) -> None:
    """Write an audit event for an ingestion action."""
    with session_scope() as s:
        write_event(
            s,
            AuditEventPayload(
                project_id=project_id,
                category="ingestion",
                action=action,
                outcome=outcome,
                details={k: str(v) for k, v in details.items()},
            ),
        )
