from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field
from typing import (
    Any,
    Generic,
    Literal,
    Mapping,
    MutableMapping,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from pydantic import ValidationError

from ..protocol.models import AlgorithmContext
from .base_model_impl import BaseModel
from .lifecycle import AlgorithmLifecycleProtocol
from .metadata import AlgorithmSpec

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)
ExecutionErrorKind = Literal["validation", "timeout", "rejected", "runtime",
                             "system"]


@dataclass(slots=True)
class ExecutionError:
    """Standardized execution error envelope."""

    kind: ExecutionErrorKind
    message: str
    details: Mapping[str, Any] | None = None
    traceback: str | None = None


@dataclass(slots=True)
class ExecutionRequest(Generic[TInput, TOutput]):
    """
    Execution payload passed into an executor.

    timeout_s is optional and overrides spec.execution.timeout_s when provided.
    """

    spec: AlgorithmSpec[TInput, TOutput]
    payload: TInput | Mapping[str, Any]
    request_id: str
    trace_id: str | None = None
    context: AlgorithmContext | None = None
    timeout_s: int | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if self.timeout_s is not None and self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive when provided")

    def effective_timeout(self) -> int | None:
        """Return the effective timeout combining request and spec hints."""

        return self.timeout_s if self.timeout_s is not None else self.spec.execution.timeout_s


@dataclass(slots=True)
class ExecutionResult(Generic[TOutput]):
    """Result metadata produced by an executor."""

    success: bool
    data: TOutput | None = None
    error: ExecutionError | None = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None
    worker_pid: int | None = None

    @property
    def duration_ms(self) -> float | None:
        """Return execution duration in milliseconds when available."""

        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at) * 1000


@runtime_checkable
class ExecutorProtocol(Protocol):
    """Contract for executing registered algorithms."""

    def submit(self, request: ExecutionRequest[Any, Any]) -> ExecutionResult[Any]:
        ...

    def start(self) -> None:
        ...

    def shutdown(self, *, wait: bool = True) -> None:
        ...


class InProcessExecutor(ExecutorProtocol):
    """
    Synchronous executor that runs algorithms within the current process.

    This implementation is primarily intended for development and testing. It
    validates inputs/outputs against AlgorithmSpec and drives lifecycle hooks
    for class-based algorithms.
    """

    def __init__(self) -> None:
        self._started = False
        self._instances: MutableMapping[tuple[str, str],
                                        AlgorithmLifecycleProtocol[Any,
                                                                   Any]] = {}

    def start(self) -> None:
        self._started = True

    def submit(self, request: ExecutionRequest[Any,
                                               Any]) -> ExecutionResult[Any]:
        if not self._started:
            self.start()

        result = ExecutionResult[Any](success=False,
                                      started_at=time.monotonic(),
                                      worker_pid=os.getpid())

        try:
            payload_model = self._coerce_input(request)
            output = self._invoke(request.spec, payload_model)
            result.data = self._coerce_output(request.spec, output)
            result.success = True
        except ValidationError as exc:
            result.error = ExecutionError(kind="validation",
                                          message=str(exc),
                                          details=self._extract_validation_details(exc))
        except TimeoutError as exc:
            result.error = ExecutionError(kind="timeout",
                                          message=str(exc))
        except Exception as exc:
            result.error = ExecutionError(kind="runtime",
                                          message=str(exc),
                                          traceback=traceback.format_exc())
        finally:
            result.ended_at = time.monotonic()

        return result

    def shutdown(self, *, wait: bool = True) -> None:
        for instance in self._instances.values():
            try:
                instance.shutdown()
            except Exception:
                # Best-effort teardown in development executor.
                continue
        self._instances.clear()
        self._started = False

    def _coerce_input(
        self, request: ExecutionRequest[Any, Any]
    ) -> BaseModel:
        payload = request.payload
        input_model = request.spec.input_model
        if isinstance(payload, input_model):
            return payload
        if isinstance(payload, Mapping):
            return input_model.model_validate(payload)
        if isinstance(payload, BaseModel):
            # Wrong model type; revalidate to ensure schema alignment.
            return input_model.model_validate(payload.model_dump())
        raise ValidationError.from_exception_data(
            "ValidationError",
            [{"type": "type_error", "loc": ("payload",), "msg": "Unsupported payload type"}],
        )

    def _coerce_output(self, spec: AlgorithmSpec[Any, Any],
                       output: Any) -> BaseModel:
        output_model = spec.output_model
        if isinstance(output, output_model):
            return output
        if isinstance(output, BaseModel):
            return output_model.model_validate(output.model_dump())
        return output_model.model_validate(output)

    def _invoke(self, spec: AlgorithmSpec[Any, Any],
                payload_model: BaseModel) -> Any:
        if spec.is_class:
            instance = self._get_instance(spec)
            result = instance.run(payload_model)
            instance.after_run()
            return result
        return spec.entrypoint(payload_model)  # type: ignore[arg-type]

    def _get_instance(
        self, spec: AlgorithmSpec[Any, Any]
    ) -> AlgorithmLifecycleProtocol[Any, Any]:
        key = spec.key()
        instance = self._instances.get(key)
        if instance is None:
            entrypoint = spec.entrypoint
            if not callable(entrypoint):
                raise TypeError(f"Entrypoint for {spec.name}:{spec.version} is not callable")
            created = entrypoint()  # type: ignore[call-arg]
            if not isinstance(created, AlgorithmLifecycleProtocol):
                raise TypeError(f"Entrypoint for {spec.name}:{spec.version} must implement lifecycle")
            created.initialize()
            self._instances[key] = created
            instance = created
        return instance

    @staticmethod
    def _extract_validation_details(exc: ValidationError) -> Any:
        try:
            return exc.errors()
        except Exception:
            return None
