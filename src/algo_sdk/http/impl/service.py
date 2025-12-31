from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from ...protocol.models import (
    AlgorithmRequest,
    AlgorithmResponse,
    api_error,
    api_success,
)

from ...core import (
    AlgorithmRegistry,
    DispatchingExecutor,
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutorProtocol,
)

ObservationStartHook = Callable[[ExecutionRequest[Any, Any]], None]
ObservationCompleteHook = Callable[
    [ExecutionRequest[Any, Any], ExecutionResult[Any]],
    None,
]

ObservationErrorHook = Callable[
    [ExecutionRequest[Any, Any], ExecutionResult[Any]],
    None,
]


@dataclass(slots=True)
class ObservationHooks:
    """Optional hooks for metrics/tracing integration."""

    on_start: ObservationStartHook | None = None
    on_complete: ObservationCompleteHook | None = None
    on_error: ObservationErrorHook | None = None


class AlgorithmHttpService:
    """
    Bridge between HTTP layer and executor/registry.

    - Picks executor (shared vs isolated) via DispatchingExecutor by default.
    - Wraps ExecutionResult into AlgorithmResponse envelope.
    - Exposes observation hooks for metrics/tracing.
    """

    def __init__(
        self,
        registry: AlgorithmRegistry,
        *,
        executor: ExecutorProtocol | None = None,
        observation: ObservationHooks | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._executor = executor or DispatchingExecutor()
        self._hooks = observation or ObservationHooks()
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    def start(self) -> None:
        self._executor.start()

    def shutdown(self) -> None:
        self._executor.shutdown()

    def invoke(
        self,
        name: str,
        version: str,
        request: AlgorithmRequest[Any],
    ) -> AlgorithmResponse[Any]:
        spec = self._registry.get(name, version)
        exec_request = ExecutionRequest(
            spec=spec,
            payload=request.data,
            request_id=request.requestId,
            request_datetime=request.datetime,
            trace_id=request.context.traceId if request.context else None,
            context=request.context,
            timeout_s=None,
        )

        self._emit_start(exec_request)
        result: ExecutionResult[Any] = self._executor.submit(exec_request)
        if result.ended_at is None:
            result.ended_at = self._now().timestamp()

        response_meta = result.response_meta
        response_context = (
            response_meta.context
            if response_meta is not None and response_meta.context is not None
            else None
        )

        if result.success:
            self._emit_complete(exec_request, result)
            code = response_meta.code if response_meta else None
            message = response_meta.message if response_meta else None
            return api_success(
                data=result.data,
                request_id=request.requestId,
                context=response_context,
                code=code if code is not None else 0,
                message=message if message is not None else "success",
            )

        self._emit_error(exec_request, result)
        error = result.error
        code, message = self._map_error(error)
        if response_meta is not None:
            if response_meta.code is not None:
                code = response_meta.code
            if response_meta.message is not None:
                message = response_meta.message
        return api_error(
            code=code,
            message=message,
            request_id=request.requestId,
            context=response_context,
        )

    def _emit_start(self, exec_request: ExecutionRequest[Any, Any]) -> None:
        if self._hooks.on_start is not None:
            self._hooks.on_start(exec_request)

    def _emit_complete(self, exec_request: ExecutionRequest[Any, Any],
                       result: ExecutionResult[Any]) -> None:
        if self._hooks.on_complete is not None:
            self._hooks.on_complete(exec_request, result)

    def _emit_error(self, exec_request: ExecutionRequest[Any, Any],
                    result: ExecutionResult[Any]) -> None:
        if self._hooks.on_error is not None:
            self._hooks.on_error(exec_request, result)

    @staticmethod
    def _map_error(error: ExecutionError | None) -> tuple[int, str]:
        if error is None:
            return 500, "unknown error"

        mapping = {
            "validation": 400,
            "rejected": 429,
            "timeout": 504,
            "runtime": 500,
            "system": 500,
        }
        code = mapping.get(error.kind, 500)
        return code, error.message
