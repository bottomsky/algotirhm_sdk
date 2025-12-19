from __future__ import annotations

import atexit
import logging
import multiprocessing as mp
import os
import queue
import time
import traceback
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Condition, Event, Lock, Thread
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
from ..runtime.context import reset_execution_context, set_execution_context
from .metadata import AlgorithmSpec

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)
ExecutionErrorKind = Literal["validation", "timeout", "rejected", "runtime",
                             "system"]

_LOGGER = logging.getLogger(__name__)


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
        spec_timeout = self.spec.execution.timeout_s
        if self.timeout_s is None:
            return spec_timeout
        if spec_timeout is None:
            return self.timeout_s
        return min(self.timeout_s, spec_timeout)


@dataclass(slots=True)
class ExecutionResult(Generic[TOutput]):
    """Result metadata produced by an executor."""

    success: bool
    data: TOutput | None = None
    error: ExecutionError | None = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None
    worker_pid: int | None = None
    queue_wait_ms: float | None = None

    @property
    def duration_ms(self) -> float | None:
        """Return execution duration in milliseconds when available."""

        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at) * 1000


def _default_max_workers() -> int:
    workers = os.cpu_count() or 1
    return max(1, workers)


def _coerce_input_model(spec: AlgorithmSpec[Any, Any],
                        payload: Any) -> BaseModel:
    input_model = spec.input_model
    if isinstance(payload, input_model):
        return payload
    if isinstance(payload, Mapping):
        return input_model.model_validate(payload)
    if isinstance(payload, BaseModel):
        return input_model.model_validate(payload.model_dump())
    raise ValidationError.from_exception_data(
        "ValidationError",
        [
            {
                "type": "type_error", "loc": ("payload",), "msg":
                "Unsupported payload type"
            }
        ],
    )


def _coerce_output_model(spec: AlgorithmSpec[Any, Any],
                         output: Any) -> BaseModel:
    output_model = spec.output_model
    if isinstance(output, output_model):
        return output
    if isinstance(output, BaseModel):
        return output_model.model_validate(output.model_dump())
    return output_model.model_validate(output)


def _extract_validation_details(exc: ValidationError) -> Any:
    try:
        return exc.errors()
    except Exception:
        return None


def _resolve_trace_id(
    trace_id: str | None,
    context: AlgorithmContext | None,
) -> str | None:
    if trace_id is not None:
        return trace_id
    if context is not None:
        return context.traceId
    return None


def _compute_queue_wait_ms(submitted_at: float,
                           started_at: float | None) -> float | None:
    if started_at is None:
        return None
    wait_ms = (started_at - submitted_at) * 1000
    return max(0.0, wait_ms)


def _build_log_extra(
    request: ExecutionRequest[Any, Any],
    result: ExecutionResult[Any],
) -> dict[str, Any]:
    trace_id = _resolve_trace_id(request.trace_id, request.context)
    extra: dict[str, Any] = {
        "request_id": request.request_id,
        "trace_id": trace_id,
        "algo_name": request.spec.name,
        "algo_version": request.spec.version,
        "worker_pid": result.worker_pid,
        "duration_ms": result.duration_ms,
        "queue_wait_ms": result.queue_wait_ms,
        "status": "success" if result.success else "error",
    }

    if request.context is not None:
        if request.context.tenantId is not None:
            extra["tenant_id"] = request.context.tenantId
        if request.context.userId is not None:
            extra["user_id"] = request.context.userId

    if result.error is not None:
        extra["error_kind"] = result.error.kind
        extra["error_message"] = result.error.message

    return extra


def _log_execution_result(request: ExecutionRequest[Any, Any],
                          result: ExecutionResult[Any]) -> None:
    extra = _build_log_extra(request, result)
    if result.success:
        _LOGGER.info("algorithm execution completed", extra=extra)
        return
    kind = result.error.kind if result.error is not None else "unknown"
    if kind in {"runtime", "system"}:
        _LOGGER.error("algorithm execution failed", extra=extra)
        return
    _LOGGER.warning("algorithm execution failed", extra=extra)


@dataclass(slots=True)
class _WorkerPayload(Generic[TInput, TOutput]):
    spec: AlgorithmSpec[TInput, TOutput]
    payload: Mapping[str, Any]
    request_id: str
    trace_id: str | None
    context: Mapping[str, Any] | None


@dataclass(slots=True)
class _WorkerResponse(Generic[TOutput]):
    success: bool
    data: Mapping[str, Any] | None
    error: ExecutionError | None
    worker_pid: int
    started_at: float
    ended_at: float


_WORKER_INSTANCES: MutableMapping[tuple[str, str],
                                  AlgorithmLifecycleProtocol[Any,
                                                             Any]] = {}


def _worker_shutdown() -> None:
    for instance in list(_WORKER_INSTANCES.values()):
        try:
            instance.shutdown()
        except Exception:
            continue
    _WORKER_INSTANCES.clear()


atexit.register(_worker_shutdown)


def _get_or_create_worker_instance(
    spec: AlgorithmSpec[Any, Any]
) -> AlgorithmLifecycleProtocol[Any, Any]:
    key = spec.key()
    instance = _WORKER_INSTANCES.get(key)
    if instance is None:
        entrypoint = spec.entrypoint
        if not callable(entrypoint):
            raise TypeError(
                f"Entrypoint for {spec.name}:{spec.version} is not callable")
        created = entrypoint()  # type: ignore[call-arg]
        if not isinstance(created, AlgorithmLifecycleProtocol):
            raise TypeError(
                f"Entrypoint for {spec.name}:{spec.version} "
                f"must implement lifecycle"
            )
        created.initialize()
        _WORKER_INSTANCES[key] = created
        instance = created
    return instance


def _worker_execute(payload: _WorkerPayload[Any, Any]) -> _WorkerResponse[Any]:
    spec = payload.spec
    started_at = time.monotonic()
    tokens = None
    try:
        try:
            context = (
                AlgorithmContext.model_validate(payload.context)
                if payload.context is not None
                else None
            )
        except ValidationError as exc:
            return _WorkerResponse(
                success=False,
                data=None,
                error=ExecutionError(
                    kind="validation",
                    message=str(exc),
                    details=_extract_validation_details(exc),
                ),
                worker_pid=os.getpid(),
                started_at=started_at,
                ended_at=time.monotonic(),
            )

        trace_id = _resolve_trace_id(payload.trace_id, context)
        tokens = set_execution_context(payload.request_id, trace_id, context)

        try:
            request_model = _coerce_input_model(spec, payload.payload)
        except ValidationError as exc:
            return _WorkerResponse(
                success=False,
                data=None,
                error=ExecutionError(
                    kind="validation",
                    message=str(exc),
                    details=_extract_validation_details(exc),
                ),
                worker_pid=os.getpid(),
                started_at=started_at,
                ended_at=time.monotonic(),
            )

        try:
            if spec.is_class:
                if spec.execution.stateful:
                    algo = _get_or_create_worker_instance(spec)
                    raw_output = algo.run(request_model)
                    algo.after_run()
                else:
                    entrypoint = spec.entrypoint
                    if not callable(entrypoint):
                        raise TypeError(
                            f"Entrypoint for {spec.name}:{spec.version} "
                            "is not callable"
                        )
                    created = entrypoint()  # type: ignore[call-arg]
                    if not isinstance(created, AlgorithmLifecycleProtocol):
                        raise TypeError(
                            f"Entrypoint for {spec.name}:{spec.version} "
                            "must implement lifecycle"
                        )
                    created.initialize()
                    try:
                        raw_output = created.run(request_model)
                        created.after_run()
                    finally:
                        try:
                            created.shutdown()
                        except Exception:
                            pass
            else:
                raw_output: AlgorithmLifecycleProtocol[Any, Any] | Any = (
                    spec.entrypoint(request_model)  # type: ignore[arg-type]
                )
        except Exception as exc:
            return _WorkerResponse(
                success=False,
                data=None,
                error=ExecutionError(
                    kind="runtime",
                    message=str(exc),
                    traceback=traceback.format_exc(),
                ),
                worker_pid=os.getpid(),
                started_at=started_at,
                ended_at=time.monotonic(),
            )

        try:
            output_model = _coerce_output_model(spec, raw_output)
        except ValidationError as exc:
            return _WorkerResponse(
                success=False,
                data=None,
                error=ExecutionError(
                    kind="validation",
                    message=str(exc),
                    details=_extract_validation_details(exc),
                ),
                worker_pid=os.getpid(),
                started_at=started_at,
                ended_at=time.monotonic(),
            )

        return _WorkerResponse(
            success=True,
            data=output_model.model_dump(),
            error=None,
            worker_pid=os.getpid(),
            started_at=started_at,
            ended_at=time.monotonic(),
        )
    finally:
        if tokens is not None:
            reset_execution_context(tokens)


def _managed_worker_loop(
    input_queue: "mp.Queue[tuple[int, _WorkerPayload[Any, Any]] | None]",
    output_queue: "mp.Queue[tuple[int, _WorkerResponse[Any]]]",
) -> None:
    while True:
        item = input_queue.get()
        if item is None:
            return
        task_id, payload = item
        response = _worker_execute(payload)
        output_queue.put((task_id, response))


@dataclass(slots=True)
class _ManagedWorker:
    index: int
    input_queue: "mp.Queue[tuple[int, _WorkerPayload[Any, Any]] | None]"
    process: mp.Process

    @property
    def pid(self) -> int | None:
        return self.process.pid


@dataclass(slots=True)
class _PendingTask(Generic[TOutput]):
    task_id: int
    worker_index: int
    submitted_at: float
    event: Event = field(default_factory=Event)
    response: _WorkerResponse[TOutput] | None = None


@runtime_checkable
class ExecutorProtocol(Protocol):
    """Contract for executing registered algorithms."""

    def submit(self, request: ExecutionRequest[Any, Any]) -> ExecutionResult[
        Any
    ]:
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

        started_at = time.monotonic()
        result = ExecutionResult[Any](success=False,
                                      started_at=started_at,
                                      worker_pid=os.getpid(),
                                      queue_wait_ms=0.0)

        context = request.context
        trace_id = _resolve_trace_id(request.trace_id, context)
        tokens = set_execution_context(request.request_id, trace_id, context)
        try:
            try:
                payload_model = _coerce_input_model(request.spec,
                                                    request.payload)
            except ValidationError as exc:
                result.error = ExecutionError(
                    kind="validation",
                    message=str(exc),
                    details=_extract_validation_details(exc),
                )
                return result

            try:
                output = self._invoke(request.spec, payload_model)
            except TimeoutError as exc:
                result.error = ExecutionError(kind="timeout",
                                              message=str(exc))
                return result
            except ValidationError as exc:
                result.error = ExecutionError(kind="runtime",
                                              message=str(exc),
                                              traceback=traceback.format_exc())
                return result
            except Exception as exc:
                result.error = ExecutionError(kind="runtime",
                                              message=str(exc),
                                              traceback=traceback.format_exc())
                return result

            try:
                result.data = _coerce_output_model(request.spec, output)
            except ValidationError as exc:
                result.error = ExecutionError(
                    kind="validation",
                    message=str(exc),
                    details=_extract_validation_details(exc),
                )
                return result

            result.success = True
            return result
        finally:
            result.ended_at = time.monotonic()
            reset_execution_context(tokens)
            _log_execution_result(request, result)

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

    def _invoke(self, spec: AlgorithmSpec[Any, Any],
                payload_model: BaseModel) -> Any:
        if spec.is_class:
            if spec.execution.stateful:
                instance = self._get_instance(spec)
                result = instance.run(payload_model)
                instance.after_run()
                return result

            entrypoint = spec.entrypoint
            if not callable(entrypoint):
                raise TypeError(
                    f"Entrypoint for {spec.name}:{spec.version} is not callable"
                )
            created = entrypoint()  # type: ignore[call-arg]
            if not isinstance(created, AlgorithmLifecycleProtocol):
                raise TypeError(
                    f"Entrypoint for {spec.name}:{spec.version} must implement lifecycle"
                )
            created.initialize()
            try:
                result = created.run(payload_model)
                created.after_run()
                return result
            finally:
                try:
                    created.shutdown()
                except Exception:
                    pass
        return spec.entrypoint(payload_model)  # type: ignore[arg-type]

    def _get_instance(
        self, spec: AlgorithmSpec[Any, Any]
    ) -> AlgorithmLifecycleProtocol[Any, Any]:
        key = spec.key()
        instance = self._instances.get(key)
        if instance is None:
            entrypoint = spec.entrypoint
            if not callable(entrypoint):
                raise TypeError(
                    f"Entrypoint for {spec.name}:{spec.version} "
                    "is not callable"
                )
            created = entrypoint()  # type: ignore[call-arg]
            if not isinstance(created, AlgorithmLifecycleProtocol):
                raise TypeError(
                    f"Entrypoint for {spec.name}:{spec.version} "
                    "must implement lifecycle"
                )
            created.initialize()
            self._instances[key] = created
            instance = created
        return instance


class ProcessPoolExecutor(ExecutorProtocol):
    """
    Shared supervised process pool executor honoring execution hints.

    This executor provides hard timeouts by terminating and restarting a worker
    process when a task exceeds its deadline. This ensures CPU/GPU resources
    are released with the process.
    """

    def __init__(self,
                 *,
                 max_workers: int | None = None,
                 queue_size: int | None = None,
                 kill_grace_s: float = 0.2,
                 poll_interval_s: float = 0.05) -> None:
        self._max_workers = max_workers or _default_max_workers()
        self._queue_size = queue_size
        self._kill_grace_s = max(0.0, kill_grace_s)
        self._poll_interval_s = max(0.01, poll_interval_s)
        self._started = False
        self._lock = Lock()
        self._ctx = mp.get_context("spawn")
        self._output_queue: "mp.Queue[object]" | None = None
        self._workers: list[_ManagedWorker] = []
        self._idle_workers: list[int] = []
        self._worker_cond = Condition(Lock())
        self._pending: dict[int, _PendingTask[Any]] = {}
        self._pending_lock = Lock()
        self._listener: Thread | None = None
        self._stop_event = Event()
        self._task_counter = 0
        slots = queue_size if queue_size is not None else self._max_workers * 2
        self._semaphore = BoundedSemaphore(value=max(1, slots))

    def start(self) -> None:
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            self._output_queue = self._ctx.Queue()
            self._workers = []
            self._idle_workers = []
            for index in range(self._max_workers):
                self._workers.append(self._spawn_worker(index))
                self._idle_workers.append(index)

            self._stop_event.clear()
            self._listener = Thread(
                target=self._listen_results,
                name="algo-sdk-process-pool-listener",
                daemon=True,
            )
            self._listener.start()
            self._started = True

    def submit(self, request: ExecutionRequest[Any,
                                               Any]) -> ExecutionResult[Any]:
        if not self._started:
            self.start()
        if self._output_queue is None:
            raise RuntimeError("process pool failed to start")

        submitted_at = time.monotonic()
        result = ExecutionResult[Any](success=False,
                                      started_at=submitted_at)
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            result.error = ExecutionError(
                kind="rejected",
                message="process pool queue is full",
            )
            result.ended_at = time.monotonic()
            result.queue_wait_ms = 0.0
            _log_execution_result(request, result)
            return result

        timeout = request.effective_timeout()
        deadline = (
            submitted_at + timeout
            if timeout is not None else None
        )

        try:
            payload_model = _coerce_input_model(request.spec, request.payload)
            payload_data = payload_model.model_dump()
            context_data = (
                request.context.model_dump()
                if request.context is not None else None
            )
            worker_index = self._acquire_worker(deadline)
            if worker_index is None:
                result.error = ExecutionError(
                    kind="timeout",
                    message="request timed out before execution started",
                )
                return result

            task_id = self._next_task_id()
            pending: _PendingTask[Any] = _PendingTask(
                task_id=task_id,
                worker_index=worker_index,
                submitted_at=submitted_at,
            )
            with self._pending_lock:
                self._pending[task_id] = pending

            payload = _WorkerPayload(
                spec=request.spec,
                payload=payload_data,
                request_id=request.request_id,
                trace_id=request.trace_id,
                context=context_data,
            )
            self._workers[worker_index].input_queue.put((task_id, payload))

            worker_response = self._wait_for_task(
                pending,
                deadline=deadline,
            )
            if worker_response is None:
                worker_pid = self._workers[worker_index].pid
                self._restart_worker(worker_index)
                result.worker_pid = worker_pid
                result.error = ExecutionError(
                    kind="timeout",
                    message="execution exceeded configured timeout",
                )
                return result

            result.worker_pid = worker_response.worker_pid
            result.started_at = worker_response.started_at
            result.ended_at = worker_response.ended_at
            result.queue_wait_ms = _compute_queue_wait_ms(
                submitted_at,
                worker_response.started_at,
            )
            if worker_response.success:
                result.data = _coerce_output_model(
                    request.spec,
                    worker_response.data or {},
                )
                result.success = True
            else:
                result.error = worker_response.error
            return result
        except ValidationError as exc:
            result.error = ExecutionError(
                kind="validation",
                message=str(exc),
                details=_extract_validation_details(exc),
            )
            return result
        except Exception as exc:
            result.error = ExecutionError(kind="system",
                                          message=str(exc),
                                          traceback=traceback.format_exc())
            return result
        finally:
            if result.ended_at is None:
                result.ended_at = time.monotonic()
            if result.queue_wait_ms is None:
                result.queue_wait_ms = _compute_queue_wait_ms(
                    submitted_at,
                    result.started_at,
                )
            _log_execution_result(request, result)
            self._semaphore.release()

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            if self._output_queue is not None:
                try:
                    self._output_queue.put(None)
                except Exception:
                    pass
            if self._listener is not None:
                self._listener.join(timeout=1.0)
            for worker in list(self._workers):
                try:
                    worker.input_queue.put(None)
                except Exception:
                    pass
            for worker in list(self._workers):
                self._terminate_process(worker.process)
            self._workers.clear()
            self._idle_workers.clear()
            with self._pending_lock:
                self._pending.clear()
            self._output_queue = None
            self._listener = None
        self._started = False

    def _spawn_worker(self, index: int) -> _ManagedWorker:
        if self._output_queue is None:
            raise RuntimeError("output queue not initialised")
        input_queue: "mp.Queue[tuple[int, _WorkerPayload[Any, Any]] | None]" = (
            self._ctx.Queue()
        )
        process = self._ctx.Process(
            target=_managed_worker_loop,
            args=(input_queue, self._output_queue),
            name=f"algo-sdk-worker-{index}",
        )
        process.start()
        return _ManagedWorker(index=index, input_queue=input_queue, process=process)

    def _terminate_process(self, process: mp.Process) -> None:
        if not process.is_alive():
            return
        try:
            process.terminate()
            process.join(timeout=self._kill_grace_s)
        except Exception:
            return
        if process.is_alive():
            try:
                process.kill()
            except Exception:
                return
            try:
                process.join(timeout=self._kill_grace_s)
            except Exception:
                return

    def _restart_worker(self, index: int) -> None:
        with self._lock:
            if not self._started:
                return
            old = self._workers[index]
            self._terminate_process(old.process)
            self._workers[index] = self._spawn_worker(index)
        with self._worker_cond:
            self._idle_workers.append(index)
            self._worker_cond.notify()

    def _acquire_worker(self, deadline: float | None) -> int | None:
        with self._worker_cond:
            while not self._idle_workers:
                if deadline is None:
                    self._worker_cond.wait(timeout=self._poll_interval_s)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self._worker_cond.wait(timeout=min(self._poll_interval_s,
                                                       remaining))
            return self._idle_workers.pop(0)

    def _release_worker(self, worker_index: int) -> None:
        with self._worker_cond:
            self._idle_workers.append(worker_index)
            self._worker_cond.notify()

    def _next_task_id(self) -> int:
        with self._lock:
            self._task_counter += 1
            return self._task_counter

    def _listen_results(self) -> None:
        if self._output_queue is None:
            return
        while not self._stop_event.is_set():
            try:
                item = self._output_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                return
            task_id, response = item  # type: ignore[misc]
            with self._pending_lock:
                pending = self._pending.get(task_id)
                if pending is None:
                    continue
                pending.response = response
                pending.event.set()
            self._release_worker(pending.worker_index)

    def _wait_for_task(
        self,
        pending: _PendingTask[Any],
        *,
        deadline: float | None,
    ) -> _WorkerResponse[Any] | None:
        worker_index = pending.worker_index
        while True:
            if pending.event.is_set():
                with self._pending_lock:
                    self._pending.pop(pending.task_id, None)
                return pending.response

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    with self._pending_lock:
                        self._pending.pop(pending.task_id, None)
                    return None
                wait_s = min(self._poll_interval_s, remaining)
            else:
                wait_s = self._poll_interval_s

            pending.event.wait(timeout=wait_s)
            process = self._workers[worker_index].process
            if not process.is_alive():
                with self._pending_lock:
                    self._pending.pop(pending.task_id, None)
                self._restart_worker(worker_index)
                pending.response = _WorkerResponse(
                    success=False,
                    data=None,
                    error=ExecutionError(
                        kind="system",
                        message="worker process crashed",
                    ),
                    worker_pid=process.pid or -1,
                    started_at=pending.submitted_at,
                    ended_at=time.monotonic(),
                )
                return pending.response


class IsolatedProcessPoolExecutor(ExecutorProtocol):
    """
    Process pools isolated per algorithm, honoring per-spec max workers.
    """

    def __init__(
            self,
            *,
            default_max_workers: int | None = None,
            queue_size: int | None = None) -> None:
        self._default_max_workers = (
            default_max_workers or _default_max_workers()
        )
        self._queue_size = queue_size
        self._executors: MutableMapping[tuple[str, str],
                                        ProcessPoolExecutor] = {}
        self._lock = Lock()
        self._started = False

    def start(self) -> None:
        self._started = True

    def submit(self, request: ExecutionRequest[Any,
                                               Any]) -> ExecutionResult[Any]:
        if not self._started:
            self.start()

        key = request.spec.key()
        executor = self._get_executor(key, request.spec)
        return executor.submit(request)

    def shutdown(self, *, wait: bool = True) -> None:
        for executor in list(self._executors.values()):
            executor.shutdown(wait=wait)
        self._executors.clear()
        self._started = False

    def _get_executor(
        self, key: tuple[str, str],
        spec: AlgorithmSpec[Any, Any]
    ) -> ProcessPoolExecutor:
        existing = self._executors.get(key)
        if existing is not None:
            return existing
        with self._lock:
            existing = self._executors.get(key)
            if existing is not None:
                return existing
            workers = spec.execution.max_workers or self._default_max_workers
            executor = ProcessPoolExecutor(max_workers=workers,
                                           queue_size=self._queue_size)
            executor.start()
            self._executors[key] = executor
            return executor


class DispatchingExecutor(ExecutorProtocol):
    """
    Route requests to shared or isolated pools based on AlgorithmSpec hints.
    """

    def __init__(
        self,
        *,
        global_max_workers: int | None = None,
        global_queue_size: int | None = None,
        isolated_default_max_workers: int | None = None,
        isolated_queue_size: int | None = None,
    ) -> None:
        default_workers = global_max_workers or _default_max_workers()
        self._shared = ProcessPoolExecutor(max_workers=default_workers,
                                           queue_size=global_queue_size)
        self._isolated = IsolatedProcessPoolExecutor(
            default_max_workers=isolated_default_max_workers
            or default_workers,
            queue_size=isolated_queue_size)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._shared.start()
        self._isolated.start()
        self._started = True

    def submit(self, request: ExecutionRequest[Any,
                                               Any]) -> ExecutionResult[Any]:
        if not self._started:
            self.start()
        if request.spec.execution.isolated_pool:
            return self._isolated.submit(request)
        return self._shared.submit(request)

    def shutdown(self, *, wait: bool = True) -> None:
        self._shared.shutdown(wait=wait)
        self._isolated.shutdown(wait=wait)
        self._started = False
