"""Telemetry — OpenTelemetry stubs.

In Phase 1 we register the API surface so call sites can emit spans/metrics
from day one, but the actual OTLP exporter is a no-op until Phase 11 wires
up a real collector. This avoids retrofitting instrumentation later.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Context manager that records a span.

    Phase 1: no-op. Phase 11: real OTEL span via ``opentelemetry-api``.
    Call sites should use this liberally; the cost is negligible.
    """
    # Deliberately minimal — attributes are accepted so call sites can be
    # instrumented now without rewriting later.
    _ = (name, attributes)
    yield


def counter(name: str, value: int = 1, **attributes: Any) -> None:
    """Increment a counter metric. Phase 1: no-op."""
    _ = (name, value, attributes)


def histogram(name: str, value: float, **attributes: Any) -> None:
    """Record a histogram observation. Phase 1: no-op."""
    _ = (name, value, attributes)
