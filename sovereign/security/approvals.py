"""Human-in-the-loop approval queue.

High-impact actions (risk recommendations, deliverable sending, external
research) require human approval before execution. This module provides:

- ``ApprovalRequest``: a request for human approval.
- ``ApprovalQueue``: manages pending/approved/rejected requests.
- ``ApprovalStatus``: pending/approved/rejected/modified.

The agent system checks this queue before executing high-impact actions.
If approval is needed, the workflow pauses (LangGraph interrupt) and
resumes when a human decides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from sovereign.core.ids import new_ulid

ApprovalStatus = Literal["pending", "approved", "rejected", "modified"]


class ApprovalRequest(BaseModel):
    """A request for human approval of a high-impact action."""

    request_id: str = ""
    workflow_id: str = ""
    project_id: str = ""
    user_id: str = ""  # who initiated the request
    action_type: str = ""  # "risk_recommendation", "deliverable_send", "external_research"
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = "pending"
    created_at: str = ""
    decided_at: str | None = None
    decided_by: str | None = None  # user_id of the approver
    modification_notes: str = ""  # if status="modified", what changed

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if not self.request_id:
            self.request_id = new_ulid()
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


class ApprovalQueue:
    """In-memory approval queue.

    Phase 11 v1: in-memory. Prod uses the database (Approval table) +
    notifications.
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def submit(self, request: ApprovalRequest) -> str:
        """Submit a new approval request. Returns the request_id."""
        self._requests[request.request_id] = request
        return request.request_id

    def get(self, request_id: str) -> ApprovalRequest | None:
        """Get a request by ID."""
        return self._requests.get(request_id)

    def list_pending(self, project_id: str | None = None) -> list[ApprovalRequest]:
        """List pending requests, optionally filtered by project."""
        result = [
            r for r in self._requests.values()
            if r.status == "pending"
            and (project_id is None or r.project_id == project_id)
        ]
        return sorted(result, key=lambda r: r.created_at)

    def list_all(self, project_id: str | None = None) -> list[ApprovalRequest]:
        """List all requests, optionally filtered by project."""
        result = [
            r for r in self._requests.values()
            if project_id is None or r.project_id == project_id
        ]
        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def approve(self, request_id: str, decided_by: str) -> ApprovalRequest:
        """Approve a request."""
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"approval request not found: {request_id}")
        if req.status != "pending":
            raise ValueError(f"request already decided: {req.status}")

        req.status = "approved"
        req.decided_at = datetime.now(UTC).isoformat()
        req.decided_by = decided_by
        return req

    def reject(self, request_id: str, decided_by: str, reason: str = "") -> ApprovalRequest:
        """Reject a request."""
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"approval request not found: {request_id}")
        if req.status != "pending":
            raise ValueError(f"request already decided: {req.status}")

        req.status = "rejected"
        req.decided_at = datetime.now(UTC).isoformat()
        req.decided_by = decided_by
        req.modification_notes = reason
        return req

    def modify(
        self,
        request_id: str,
        decided_by: str,
        modifications: str,
        new_details: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Approve with modifications."""
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"approval request not found: {request_id}")
        if req.status != "pending":
            raise ValueError(f"request already decided: {req.status}")

        req.status = "modified"
        req.decided_at = datetime.now(UTC).isoformat()
        req.decided_by = decided_by
        req.modification_notes = modifications
        if new_details:
            req.details.update(new_details)
        return req

    @property
    def pending_count(self) -> int:
        return sum(1 for r in self._requests.values() if r.status == "pending")


# Singleton
_queue: ApprovalQueue | None = None


def get_approval_queue() -> ApprovalQueue:
    """Return the cached ApprovalQueue singleton."""
    global _queue  # noqa: PLW0603
    if _queue is None:
        _queue = ApprovalQueue()
    return _queue


def reset_approval_queue() -> None:
    """Test helper: drop the cached queue."""
    global _queue  # noqa: PLW0603
    _queue = None
