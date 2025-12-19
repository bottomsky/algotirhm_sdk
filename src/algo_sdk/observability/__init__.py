from __future__ import annotations

from typing import Any, Protocol

from ..core.executor import ExecutionRequest, ExecutionResult
from ..http import ObservationHooks
from .metrics import (
    AlgorithmMetricsSnapshot,
    HistogramSnapshot,
    InMemoryMetrics,
)
from .tracing import InMemoryTracer, Span


class ObservationRecorder(Protocol):
    def on_start(self, request: ExecutionRequest[Any, Any]) -> None:
        ...

    def on_complete(self, request: ExecutionRequest[Any, Any],
                    result: ExecutionResult[Any]) -> None:
        ...

    def on_error(self, request: ExecutionRequest[Any, Any],
                 result: ExecutionResult[Any]) -> None:
        ...


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
    "create_observation_hooks",
]
