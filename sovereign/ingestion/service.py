"""Ingestion service — secure upload, validation, quarantine, parsing.

MongoDB-backed (Phase 14 update: replaced SQLAlchemy with PyMongo).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sovereign.audit.chain import AuditEventPayload
from sovereign.audit.log import write_event
from sovereign.core.errors import NotFoundError
from sovereign.core.ids import new_ulid, utcnow
from sovereign.core.logging import get_logger
from sovereign.parsing.model import ParsedDocument
from sovereign.parsing.registry import parse_document, supported_mimes
from sovereign.storage.db.base import COLLECTIONS, session_scope
from sovereign.storage.db.models import new_document
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
    (b"\x50\x4b\x03\x04", "application/zip"),
    (b"\xd0\xcf\x11\xe0", "application/msoffice"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),
]


def _detect_mime(data: bytes, filename: str, client_mime: str) -> str:
    for magic, mime in _MAGIC_BYTES:
        if data[:len(magic)] == magic:
            if mime == "application/zip":
                if _is_docx(data):
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if _is_xlsx(data):
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                return mime
            if mime == "image/webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                continue
            return mime
    try:
        data.decode("utf-8")
        if filename.endswith(".md") or filename.endswith(".markdown"):
            return "text/markdown"
        if filename.endswith(".csv"):
            return "text/csv"
        return "text/plain"
    except UnicodeDecodeError:
        pass
    log.warning("ingestion.mime.fallback", filename=filename, client_mime=client_mime)
    return client_mime or "application/octet-stream"


def _is_docx(data: bytes) -> bool:
    return b"word/" in data[:2048]


def _is_xlsx(data: bytes) -> bool:
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
    warnings: list[str] = []
    size = len(data)
    if size == 0:
        return ValidationResult(
            is_valid=False, mime_type="", sha256="", size_bytes=0,
            quarantine_reason="empty file",
        )
    if size > max_size_mb * 1024 * 1024:
        return ValidationResult(
            is_valid=False, mime_type="", sha256="", size_bytes=size,
            quarantine_reason=f"file exceeds {max_size_mb}MB limit",
        )
    mime = _detect_mime(data, filename, client_mime)
    supported = supported_mimes()
    if mime not in supported and mime not in ("application/zip", "application/octet-stream"):
        warnings.append(f"unsupported MIME type: {mime}")
    sha256 = hashlib.sha256(data).hexdigest()
    if mime == "application/pdf":
        qpdf_warning = _check_pdf_integrity(data)
        if qpdf_warning:
            warnings.append(qpdf_warning)
    return ValidationResult(
        is_valid=True, mime_type=mime, sha256=sha256,
        size_bytes=size, warnings=warnings,
    )


def _check_pdf_integrity(data: bytes) -> str | None:
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    qpdf = shutil.which("qpdf")
    if not qpdf:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            f.flush()
            result = subprocess.run(  # noqa: S603
                [qpdf, "--check", f.name],
                capture_output=True, text=True, timeout=30, check=False,
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
    document_id: str
    project_id: str
    status: str
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
    if store is None:
        store = get_object_store()

    validation = validate_document(data, filename, client_mime, max_size_mb=max_size_mb)

    if not validation.is_valid:
        quarantine_key = new_storage_key()
        store.put(project_id, quarantine_key, data)
        _audit_ingest(
            project_id=project_id, action="document.quarantine", outcome="blocked",
            filename=filename, reason=validation.quarantine_reason or "unknown",
            size=validation.size_bytes,
        )
        return IngestResult(
            document_id="", project_id=project_id, status="quarantined",
            mime_type=validation.mime_type, sha256=validation.sha256,
            size_bytes=validation.size_bytes, version=0,
            quarantine_reason=validation.quarantine_reason,
        )

    # 2. Dedup check (MongoDB)
    with session_scope() as db:
        existing = db[COLLECTIONS["documents"]].find_one({
            "project_id": project_id,
            "sha256": validation.sha256,
        })

    if existing:
        _audit_ingest(
            project_id=project_id, action="document.duplicate", outcome="success",
            filename=filename, sha256=validation.sha256, existing_doc_id=existing["id"],
        )
        return IngestResult(
            document_id=existing["id"], project_id=project_id, status="duplicate",
            mime_type=existing["mime_type"], sha256=validation.sha256,
            size_bytes=validation.size_bytes, version=existing["version"],
            is_duplicate=True,
        )

    # 3. Store raw bytes
    storage_key = new_storage_key()
    store.put(project_id, storage_key, data)

    # 4. Parse (or OCR for scanned PDFs / images)
    doc_id = new_ulid()
    parse_warnings: list[str] = list(validation.warnings)
    parsed: ParsedDocument | None = None

    if validation.mime_type.startswith("image/"):
        try:
            from sovereign.ocr.pipeline import OCROptions, ocr_image
            parsed = await ocr_image(
                image_data=data, filename=filename,
                media_type=validation.mime_type, options=OCROptions(),
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
    elif validation.mime_type == "application/pdf":
        try:
            from sovereign.ocr.pipeline import detect_scanned_pdf
            scan_report = detect_scanned_pdf(data)
            if scan_report.any_scanned:
                from sovereign.ocr.pipeline import OCROptions, ocr_pdf
                parsed = await ocr_pdf(
                    pdf_data=data, filename=filename, options=OCROptions(),
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
                parsed = parse_document(data, filename, validation.mime_type)
                parsed.document_id = doc_id
                parsed.project_id = project_id
                parsed.source_sha256 = validation.sha256
                parse_warnings.extend(parsed.parse_warnings)
        except Exception as e:
            log.error(
                "ingestion.pdf_ocr.failed",
                document_id=doc_id, filename=filename, error=str(e),
            )
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
        try:
            parsed = parse_document(data, filename, validation.mime_type)
            parsed.document_id = doc_id
            parsed.project_id = project_id
            parsed.source_sha256 = validation.sha256
            parse_warnings.extend(parsed.parse_warnings)
        except Exception as e:
            log.error("ingestion.parse.failed", document_id=doc_id, filename=filename, error=str(e))
            parse_warnings.append(f"parse failed: {e}")

    # 5. Persist Document (MongoDB)
    version = _get_next_version(project_id, filename)
    doc_status = "parsed" if parsed else "stored"
    try:
        doc_dict = new_document(
            id=doc_id,
            project_id=project_id,
            original_filename=filename,
            storage_key=storage_key,
            mime_type=validation.mime_type,
            size_bytes=validation.size_bytes,
            sha256=validation.sha256,
            status=doc_status,
            version=version,
            metadata_json=json.dumps({
                "parse_warnings": parse_warnings,
                "parsed_at": utcnow().isoformat(),
                "word_count": parsed.metadata.word_count if parsed else 0,
                "page_count": parsed.metadata.page_count if parsed else 0,
            }),
        )

        with session_scope() as db:
            db[COLLECTIONS["documents"]].insert_one(doc_dict)
            write_event(
                db,
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
                        "status": doc_status,
                        "parse_warnings": parse_warnings[:5],
                    },
                ),
            )
    except Exception as e:
        log.error("ingestion.persist.failed", document_id=doc_id, error=str(e), exc_info=True)
        return IngestResult(
            document_id=doc_id, project_id=project_id, status="stored",
            mime_type=validation.mime_type, sha256=validation.sha256,
            size_bytes=validation.size_bytes, version=version,
            parse_warnings=parse_warnings + [f"persist failed: {e}"],
        )

    # 6. Store parsed document JSON (if parse succeeded)
    if parsed:
        parsed_key = f"{storage_key}.parsed.json"
        store.put(project_id, parsed_key, parsed.model_dump_json().encode("utf-8"))

        # 7. Index into the knowledge base
        try:
            from sovereign.embeddings.indexing import get_indexing_service
            indexing = get_indexing_service()
            index_result = await indexing.index_document(
                project_id=project_id, document_id=doc_id, parsed=parsed,
            )
            if index_result.status == "indexed":
                log.info("ingestion.indexed", document_id=doc_id, chunks=index_result.chunk_count)
                with session_scope() as db:
                    db[COLLECTIONS["documents"]].update_one(
                        {"id": doc_id}, {"$set": {"status": "indexed"}}
                    )
                doc_status = "indexed"
            else:
                parse_warnings.append(f"indexing failed: {index_result.error}")
        except Exception as e:
            log.error("ingestion.index_failed", document_id=doc_id, error=str(e))
            parse_warnings.append(f"indexing failed: {e}")

    log.info(
        "ingestion.complete", document_id=doc_id, project_id=project_id,
        filename=filename, status=doc_status, size=validation.size_bytes,
    )

    return IngestResult(
        document_id=doc_id, project_id=project_id, status=doc_status,
        mime_type=validation.mime_type, sha256=validation.sha256,
        size_bytes=validation.size_bytes, version=version,
        parse_warnings=parse_warnings,
    )


# ---------------------------------------------------------------------------
# Document CRUD (MongoDB)
# ---------------------------------------------------------------------------
class Document:
    """Simple wrapper for a MongoDB document dict, providing attribute access."""
    def __init__(self, data: dict[str, Any]) -> None:
        self.id = data.get("id", "")
        self.project_id = data.get("project_id", "")
        self.original_filename = data.get("original_filename", "")
        self.storage_key = data.get("storage_key", "")
        self.mime_type = data.get("mime_type", "")
        self.size_bytes = data.get("size_bytes", 0)
        self.sha256 = data.get("sha256", "")
        self.status = data.get("status", "uploaded")
        self.version = data.get("version", 1)
        self.metadata_json = data.get("metadata_json")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        return cls(data)


def get_document(project_id: str, document_id: str) -> Document:
    with session_scope() as db:
        doc = db[COLLECTIONS["documents"]].find_one({
            "id": document_id,
            "project_id": project_id,
        })
        if doc is None:
            msg = f"document not found: {document_id}"
            raise NotFoundError(msg)
        return Document.from_dict(doc)


def get_parsed_document(
    project_id: str, document_id: str, store: ObjectStore | None = None
) -> ParsedDocument:
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
    with session_scope() as db:
        cursor = (
            db[COLLECTIONS["documents"]]
            .find({"project_id": project_id})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [Document.from_dict(doc) for doc in cursor]


def delete_document(project_id: str, document_id: str) -> None:
    store = get_object_store()

    with session_scope() as db:
        doc = db[COLLECTIONS["documents"]].find_one({
            "id": document_id,
            "project_id": project_id,
        })
        if doc is None:
            msg = f"document not found: {document_id}"
            raise NotFoundError(msg)

        storage_key = doc["storage_key"]
        db[COLLECTIONS["documents"]].delete_one({"id": document_id})

        write_event(
            db,
            AuditEventPayload(
                project_id=project_id,
                category="ingestion",
                action="document.delete",
                outcome="success",
                details={"document_id": document_id, "filename": doc["original_filename"]},
            ),
        )

    store.delete(project_id, storage_key)
    store.delete(project_id, f"{storage_key}.parsed.json")

    try:
        from sovereign.embeddings.indexing import get_indexing_service
        indexing = get_indexing_service()
        indexing.remove_document(project_id, document_id)
    except Exception as e:
        log.warning("ingestion.delete.index_cleanup_failed", document_id=document_id, error=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_next_version(project_id: str, filename: str) -> int:
    with session_scope() as db:
        cursor = (
            db[COLLECTIONS["documents"]]
            .find({"project_id": project_id, "original_filename": filename})
            .sort("version", -1)
            .limit(1)
        )
        docs = list(cursor)
        return (docs[0]["version"] + 1) if docs else 1


def _audit_ingest(
    project_id: str,
    action: str,
    outcome: str,
    **details: object,
) -> None:
    with session_scope() as db:
        write_event(
            db,
            AuditEventPayload(
                project_id=project_id,
                category="ingestion",
                action=action,
                outcome=outcome,
                details={k: str(v) for k, v in details.items()},
            ),
        )
