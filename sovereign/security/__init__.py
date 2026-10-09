"""Security — auth, RBAC, egress gateway, sandbox, prompt injection defense."""
from sovereign.security.approvals import ApprovalQueue, ApprovalRequest, ApprovalStatus
from sovereign.security.auth import AuthService, create_token, verify_token
from sovereign.security.egress import EgressGateway, EgressRequest
from sovereign.security.injection import InjectionGuard
from sovereign.security.rbac import Permission, RBACService, Role
from sovereign.security.sandbox import Sandbox, ToolResult

__all__ = [
    "ApprovalQueue",
    "ApprovalRequest",
    "ApprovalStatus",
    "AuthService",
    "EgressGateway",
    "EgressRequest",
    "InjectionGuard",
    "Permission",
    "RBACService",
    "Role",
    "Sandbox",
    "ToolResult",
    "create_token",
    "verify_token",
]
