"""RBAC — role-based access control.

Three roles: admin, analyst, viewer. Each has a set of permissions.
Project isolation is enforced by checking project_id membership in the
JWT token's ``projects`` claim.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from sovereign.core.errors import AuthorizationError

Role = Literal["admin", "analyst", "viewer"]


class Permission(str, Enum):
    """Permissions that can be granted to roles."""

    # Document operations
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_READ = "document.read"
    DOCUMENT_DELETE = "document.delete"

    # Knowledge base
    KB_SEARCH = "kb.search"
    KB_INDEX = "kb.index"

    # RAG
    RAG_QUERY = "rag.query"

    # Agent
    AGENT_RUN = "agent.run"

    # Deliverables
    DELIVERABLE_CREATE = "deliverable.create"
    DELIVERABLE_EXPORT = "deliverable.export"

    # Admin
    USER_MANAGE = "user.manage"
    AUDIT_READ = "audit.read"
    APPROVAL_DECIDE = "approval.decide"

    # Research (egress)
    RESEARCH_EXTERNAL = "research.external"


# Role → permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    "viewer": {
        Permission.DOCUMENT_READ,
        Permission.KB_SEARCH,
        Permission.RAG_QUERY,
        Permission.DELIVERABLE_EXPORT,
    },
    "analyst": {
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE,
        Permission.KB_SEARCH,
        Permission.KB_INDEX,
        Permission.RAG_QUERY,
        Permission.AGENT_RUN,
        Permission.DELIVERABLE_CREATE,
        Permission.DELIVERABLE_EXPORT,
        Permission.RESEARCH_EXTERNAL,
    },
    "admin": set(Permission),  # all permissions
}


class RBACService:
    """Role-based access control service.

    Usage::

        rbac = RBACService()
        rbac.check_permission(role="viewer", permission=Permission.DOCUMENT_READ)
        rbac.check_project_access(role="analyst", token_projects=["proj_1"], project_id="proj_1")
    """

    def check_permission(self, role: Role, permission: Permission) -> None:
        """Check if a role has a permission. Raises AuthorizationError if not."""
        allowed = ROLE_PERMISSIONS.get(role, set())
        if permission not in allowed:
            raise AuthorizationError(
                f"role '{role}' does not have permission '{permission.value}'"
            )

    def has_permission(self, role: Role, permission: Permission) -> bool:
        """Check if a role has a permission (non-raising)."""
        return permission in ROLE_PERMISSIONS.get(role, set())

    def check_project_access(
        self,
        role: Role,
        token_projects: list[str],
        project_id: str,
    ) -> None:
        """Check if the user can access a specific project.

        Admins can access all projects. Other roles must have the project
        in their token's ``projects`` list.
        """
        if role == "admin":
            return  # admin sees all

        if project_id not in token_projects:
            raise AuthorizationError(
                f"access denied to project '{project_id}'"
            )

    def get_permissions(self, role: Role) -> set[Permission]:
        """Return all permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())
