"""Egress gateway — controlled outbound HTTP.

OFF BY DEFAULT. Even when enabled, only allow-listed hosts are reachable.
This is the ONLY outbound HTTP path in SOVEREIGN. The Research Agent uses
it exclusively; it has NO KB access.

Security: the egress gateway exists to prevent confidential data from
leaving the organization. Even if an agent is compromised, it cannot
exfiltrate data without going through this gateway, which checks:
1. Egress is enabled (EGRESS_ENABLED=true)
2. The target host is in the allow-list (configs/policies.yaml)
3. The request is logged for audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import yaml

from sovereign.core.config import get_settings
from sovereign.core.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class EgressRequest:
    """An outbound HTTP request."""

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 30.0


@dataclass(slots=True)
class EgressResult:
    """Result of an egress request."""

    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""


class EgressGateway:
    """Controlled outbound HTTP gateway.

    Usage::

        gw = EgressGateway()
        result = gw.request(EgressRequest(url="https://api.example.com/data"))
        if result.blocked:
            print(f"blocked: {result.block_reason}")
    """

    def __init__(self, allowlist_path: str | None = None) -> None:
        self._allowlist: list[dict[str, Any]] = []
        self._enabled = False
        self._loaded = False
        self._allowlist_path = allowlist_path

    def _load_config(self) -> None:
        """Load egress config from policies.yaml."""
        if self._loaded:
            return

        settings = get_settings()
        self._enabled = settings.egress_enabled

        path = self._allowlist_path or str(settings.egress_allowlist_path)
        try:
            with open(path, encoding="utf-8") as f:
                policies = yaml.safe_load(f) or {}
            egress_config = policies.get("egress", {}) or {}
            self._enabled = egress_config.get("enabled", self._enabled)
            self._allowlist = egress_config.get("allowlist", []) or []
        except Exception as e:
            log.warning("egress.config_load_failed", error=str(e))
            self._allowlist = []

        self._loaded = True
        log.info("egress.config_loaded", enabled=self._enabled, allowlist_size=len(self._allowlist))

    def is_allowed(self, url: str) -> tuple[bool, str]:
        """Check if a URL is allowed by the egress policy.

        Returns (allowed, reason).
        """
        self._load_config()

        if not self._enabled:
            return (False, "egress is disabled (off by default)")

        # Parse the URL to extract host
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""

        if not host:
            return (False, "invalid URL: no host")

        for entry in self._allowlist:
            allowed_host = entry.get("host", "")
            if host == allowed_host or host.endswith("." + allowed_host):
                return (True, f"allowed by policy: {entry.get('reason', '')}")

        return (False, f"host '{host}' not in allowlist")

    def request(self, req: EgressRequest) -> EgressResult:
        """Execute an egress request.

        If egress is disabled or the host is not allow-listed, returns
        an EgressResult with blocked=True. Otherwise, executes the request
        and returns the response.
        """
        allowed, reason = self.is_allowed(req.url)

        if not allowed:
            log.warning("egress.blocked", url=req.url, reason=reason)
            return EgressResult(
                status_code=0,
                body=b"",
                blocked=True,
                block_reason=reason,
            )

        # Execute the request
        try:
            with httpx.Client(timeout=req.timeout) as client:
                response = client.request(
                    method=req.method,
                    url=req.url,
                    headers=req.headers,
                    content=req.body,
                )

                log.info(
                    "egress.request",
                    method=req.method,
                    url=req.url,
                    status=response.status_code,
                    bytes=len(response.content),
                )

                return EgressResult(
                    status_code=response.status_code,
                    body=response.content,
                    headers=dict(response.headers),
                )

        except Exception as e:
            log.error("egress.request_failed", url=req.url, error=str(e))
            return EgressResult(
                status_code=0,
                body=b"",
                blocked=True,
                block_reason=f"request failed: {e}",
            )

    @property
    def enabled(self) -> bool:
        """Check if egress is enabled."""
        self._load_config()
        return self._enabled

    @property
    def allowlist_size(self) -> int:
        """Number of allow-listed hosts."""
        self._load_config()
        return len(self._allowlist)
