from __future__ import annotations

from typing import Any, Protocol

from ..core import ExecutionRequest, ExecutionResult


class ObservationRecorder(Protocol):
    """Protocol for components that record execution observations (metrics, tracing)."""
    def on_start(self, request: ExecutionRequest[Any, Any]) -> None:
        ...

    def on_complete(self, request: ExecutionRequest[Any, Any],
                    result: ExecutionResult[Any]) -> None:
        ...

    def on_error(self, request: ExecutionRequest[Any, Any],
                 result: ExecutionResult[Any]) -> None:
        ...
