from __future__ import annotations

from typing import Any

from ..core import ExecutionRequest, ExecutionResult
from ..http.impl.service import ObservationHooks
from .impl.metrics import (
    AlgorithmMetricsSnapshot,
    HistogramSnapshot,
    InMemoryMetrics,
    build_otel_metrics,
    render_prometheus_text,
)
from .impl.tracing import InMemoryTracer, Span
from .protocol import ObservationRecorder


def create_observation_hooks(
    *recorders: ObservationRecorder | None,
) -> ObservationHooks:
    """Build ObservationHooks that fan out to provided recorders."""

    def _on_start(request: ExecutionRequest[Any, Any]) -> None:
        for recorder in recorders:
            if recorder is not None:
                recorder.on_start(request)

    def _on_complete(request: ExecutionRequest[Any, Any],
                     result: ExecutionResult[Any]) -> None:
        for recorder in recorders:
            if recorder is not None:
                recorder.on_complete(request, result)

    def _on_error(request: ExecutionRequest[Any, Any],
                  result: ExecutionResult[Any]) -> None:
        for recorder in recorders:
            if recorder is not None:
                recorder.on_error(request, result)

    return ObservationHooks(
        on_start=_on_start,
        on_complete=_on_complete,
        on_error=_on_error,
    )


__all__ = [
    "AlgorithmMetricsSnapshot",
    "HistogramSnapshot",
    "InMemoryMetrics",
    "InMemoryTracer",
    "ObservationRecorder",
    "Span",
    "build_otel_metrics",
    "create_observation_hooks",
    "render_prometheus_text",
]
