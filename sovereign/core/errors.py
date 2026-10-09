"""SOVEREIGN error hierarchy.

All application exceptions inherit from ``SovereignError``. Each leaf class
carries a stable ``code`` string for API translation and audit logging.
Subsystems should raise the most specific leaf class available; add new
leaf classes here rather than re-raising raw stdlib exceptions.
"""

from __future__ import annotations


class SovereignError(Exception):
    """Base class for all SOVEREIGN application errors."""

    code: str = "sovereign.error"
    http_status: int = 500

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.code)
        if code:
            self.code = code
        self.message = message or self.code


# --- Configuration ---
class ConfigError(SovereignError):
    code = "sovereign.config"
    http_status = 500


# --- Security ---
class SecurityError(SovereignError):
    code = "sovereign.security"
    http_status = 403


class AuthError(SovereignError):
    code = "sovereign.auth"
    http_status = 401


class AuthorizationError(SecurityError):
    code = "sovereign.authz"
    http_status = 403


class ProjectIsolationError(SecurityError):
    code = "sovereign.project_isolation"
    http_status = 403


class PromptInjectionError(SecurityError):
    """Raised when retrieved/ingested content is detected as an attempted injection."""

    code = "sovereign.prompt_injection"
    http_status = 422


# --- Ingestion / parsing ---
class IngestionError(SovereignError):
    code = "sovereign.ingestion"
    http_status = 400


class QuarantineError(IngestionError):
    code = "sovereign.ingestion.quarantine"
    http_status = 422


class DocumentParseError(IngestionError):
    code = "sovereign.ingestion.parse"
    http_status = 422


# --- Storage ---
class StorageError(SovereignError):
    code = "sovereign.storage"
    http_status = 500


class NotFoundError(SovereignError):
    code = "sovereign.not_found"
    http_status = 404


class ConflictError(SovereignError):
    code = "sovereign.conflict"
    http_status = 409


# --- Models / ModelGateway ---
class ModelError(SovereignError):
    code = "sovereign.model"
    http_status = 502


class ModelUnavailableError(ModelError):
    code = "sovereign.model.unavailable"
    http_status = 503


# --- RAG / retrieval ---
class RetrievalError(SovereignError):
    code = "sovereign.retrieval"
    http_status = 500


class InsufficientEvidenceError(SovereignError):
    """First-class: not an LLM error, an explicit system verdict."""

    code = "sovereign.rag.insufficient_evidence"
    http_status = 200  # This is a successful "I don't know" response, not an error.


# --- Orchestration ---
class OrchestrationError(SovereignError):
    code = "sovereign.orchestration"
    http_status = 500


class WorkflowPaused(OrchestrationError):
    """HITL interrupt — not a failure, a pause awaiting human decision."""

    code = "sovereign.orchestration.paused"
    http_status = 202


# --- Audit ---
class AuditError(SovereignError):
    code = "sovereign.audit"
    http_status = 500


class AuditChainBrokenError(AuditError):
    code = "sovereign.audit.chain_broken"
    http_status = 500


# --- Egress ---
class EgressBlockedError(SecurityError):
    code = "sovereign.egress.blocked"
    http_status = 403
