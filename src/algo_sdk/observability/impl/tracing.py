from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from ...core import ExecutionRequest, ExecutionResult


@dataclass(slots=True)
class Span:
    name: str
    trace_id: str | None
    request_id: str
    algo_name: str
    algo_version: str
    tenant_id: str | None = None
    user_id: str | None = None
    status: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None
    duration_ms: float | None = None
    queue_wait_ms: float | None = None
    error_kind: str | None = None
    error_message: str | None = None


class InMemoryTracer:
    """In-memory tracing recorder for algorithm executions."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: dict[str, Span] = {}
        self._finished: list[Span] = []

    def on_start(self, request: ExecutionRequest[Any, Any]) -> None:
        span = Span(
            name="algorithm.execute",
            trace_id=request.trace_id,
            request_id=request.request_id,
            algo_name=request.spec.name,
            algo_version=request.spec.version,
            tenant_id=request.context.tenantId
            if request.context is not None else None,
            user_id=request.context.userId
            if request.context is not None else None,
        )
        with self._lock:
            self._active[request.request_id] = span

    def on_complete(self, request: ExecutionRequest[Any, Any],
                    result: ExecutionResult[Any]) -> None:
        self._finish(request, result, status="success")

    def on_error(self, request: ExecutionRequest[Any, Any],
                 result: ExecutionResult[Any]) -> None:
        self._finish(request, result, status="error")

    def spans(self, *, clear: bool = False) -> tuple[Span, ...]:
        with self._lock:
            finished = tuple(self._finished)
            if clear:
                self._finished.clear()
            return finished

    def _finish(self, request: ExecutionRequest[Any, Any],
                result: ExecutionResult[Any], *, status: str) -> None:
        with self._lock:
            span = self._active.pop(request.request_id, None)
        if span is None:
            span = Span(
                name="algorithm.execute",
                trace_id=request.trace_id,
                request_id=request.request_id,
                algo_name=request.spec.name,
                algo_version=request.spec.version,
            )

        span.status = status
        span.queue_wait_ms = result.queue_wait_ms
        span.duration_ms = result.duration_ms
        span.ended_at = result.ended_at or time.monotonic()
        if result.error is not None:
            span.error_kind = result.error.kind
            span.error_message = result.error.message
        with self._lock:
            self._finished.append(span)
