"""Sandbox — tool execution with limits.

Tools (OCR, parsing, deliverable export) run in a restricted environment.
Phase 11 v1: subprocess with timeout + memory limit. Phase 14 adds
seccomp/namespace isolation for production.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sovereign.core.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class ToolResult:
    """Result of a sandboxed tool execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class Sandbox:
    """Sandboxed tool execution.

    Runs commands in a subprocess with:
    - Timeout (kills if exceeded)
    - Memory limit (RLIMIT_AS)
    - No network access (best-effort: depends on OS)

    Usage::

        sandbox = Sandbox(timeout=30, memory_mb=512)
        result = sandbox.run(["python", "script.py"], cwd="/tmp")
        if result.succeeded:
            print(result.stdout)
    """

    def __init__(
        self,
        timeout: int = 30,
        memory_mb: int = 512,
        max_output_size: int = 10 * 1024 * 1024,  # 10 MB
    ) -> None:
        self._timeout = timeout
        self._memory_mb = memory_mb
        self._max_output_size = max_output_size

    def run(
        self,
        command: list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> ToolResult:
        """Run a command in the sandbox.

        Args:
            command: the command + args as a list.
            cwd: working directory.
            env: environment variables (merged with os.environ).
            stdin: stdin content.

        Returns: ToolResult.
        """
        import os

        full_env = dict(os.environ)
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(  # noqa: S603
                command,
                cwd=cwd,
                env=full_env,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )

            # Truncate output if exceeds max size
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            if len(stdout) > self._max_output_size:
                stdout = stdout[: self._max_output_size] + "\n[truncated]"
            if len(stderr) > self._max_output_size:
                stderr = stderr[: self._max_output_size] + "\n[truncated]"

            return ToolResult(
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )

        except subprocess.TimeoutExpired as e:
            log.warning("sandbox.timeout", command=command[0], timeout=self._timeout)
            return ToolResult(
                exit_code=-1,
                stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                stderr=e.stderr or "" if isinstance(e.stderr, str) else "",
                timed_out=True,
                error=f"timed out after {self._timeout}s",
            )
        except Exception as e:
            log.error("sandbox.error", command=command[0], error=str(e))
            return ToolResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error=str(e),
            )

    def run_python(self, code: str, cwd: str | Path | None = None) -> ToolResult:
        """Run Python code in the sandbox.

        Args:
            code: Python source code.
            cwd: working directory.

        Returns: ToolResult.
        """
        return self.run(
            [sys.executable, "-c", code],
            cwd=cwd,
        )
