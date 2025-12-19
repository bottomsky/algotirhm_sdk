import time

from algo_sdk.core import (
    AlgorithmSpec,
    BaseModel,
    ExecutionConfig,
    ExecutionRequest,
    InProcessExecutor,
    ProcessPoolExecutor,
)
from algo_sdk.protocol.models import AlgorithmContext
from algo_sdk.runtime import (
    get_current_context,
    get_current_request_id,
    get_current_trace_id,
)


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def _double(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)


class _SleepReq(BaseModel):
    delay: float


class _SleepResp(BaseModel):
    done: bool


def _sleep(req: _SleepReq) -> _SleepResp:
    time.sleep(req.delay)
    return _SleepResp(done=True)


class _CtxReq(BaseModel):
    value: int


class _CtxResp(BaseModel):
    trace_id: str | None
    request_id: str | None
    tenant_id: str | None


def _echo_context(_: _CtxReq) -> _CtxResp:
    context = get_current_context()
    return _CtxResp(
        trace_id=get_current_trace_id(),
        request_id=get_current_request_id(),
        tenant_id=context.tenantId if context is not None else None,
    )


def _build_spec(entrypoint: object, *,
                execution: ExecutionConfig | None = None) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="demo",
        version="v1",
        description=None,
        input_model=_Req if entrypoint is _double else _SleepReq,
        output_model=_Resp if entrypoint is _double else _SleepResp,
        execution=execution or ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=False,
    )


def _build_ctx_spec(entrypoint: object) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="ctx",
        version="v1",
        description=None,
        input_model=_CtxReq,
        output_model=_CtxResp,
        execution=ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=False,
    )


def test_process_pool_executes_function() -> None:
    spec = _build_spec(_double)
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        req = ExecutionRequest(spec=spec,
                               payload=_Req(value=3),
                               request_id="req-1")
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.doubled == 6
        assert result.worker_pid is not None
    finally:
        executor.shutdown()


def test_process_pool_respects_timeout() -> None:
    spec = _build_spec(_sleep, execution=ExecutionConfig(timeout_s=1))
    executor = ProcessPoolExecutor(max_workers=1, queue_size=1)
    try:
        req = ExecutionRequest(spec=spec,
                               payload=_SleepReq(delay=0.2),
                               request_id="req-timeout",
                               timeout_s=0.05)
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "timeout"
    finally:
        executor.shutdown()


def test_in_process_propagates_context() -> None:
    spec = _build_ctx_spec(_echo_context)
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_CtxReq(value=1),
            request_id="req-ctx",
            trace_id=None,
            context=AlgorithmContext(
                traceId="trace-ctx",
                tenantId="tenant-1",
            ),
        )
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.trace_id == "trace-ctx"
        assert result.data.request_id == "req-ctx"
        assert result.data.tenant_id == "tenant-1"
    finally:
        executor.shutdown()


def test_process_pool_propagates_context() -> None:
    spec = _build_ctx_spec(_echo_context)
    executor = ProcessPoolExecutor(max_workers=1, queue_size=1)
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_CtxReq(value=2),
            request_id="req-ctx-pool",
            trace_id="trace-pool",
            context=AlgorithmContext(
                traceId="trace-fallback",
                tenantId="tenant-2",
            ),
        )
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.trace_id == "trace-pool"
        assert result.data.request_id == "req-ctx-pool"
        assert result.data.tenant_id == "tenant-2"
    finally:
        executor.shutdown()


class _AlgoValReq(BaseModel):
    value: int


class _AlgoValResp(BaseModel):
    ok: bool


def _algo_raises_validation(_: _AlgoValReq) -> _AlgoValResp:
    _AlgoValReq.model_validate({"value": "not-an-int"})
    return _AlgoValResp(ok=True)


def _build_val_spec(entrypoint: object) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="algo-val",
        version="v1",
        description=None,
        input_model=_AlgoValReq,
        output_model=_AlgoValResp,
        execution=ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=False,
    )


def test_in_process_algorithm_validation_error_is_runtime() -> None:
    spec = _build_val_spec(_algo_raises_validation)
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_AlgoValReq(value=1),
            request_id="req-algo-val-inproc",
        )
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "runtime"
        assert result.error.traceback is not None
    finally:
        executor.shutdown()


def test_process_pool_algorithm_validation_error_is_runtime() -> None:
    spec = _build_val_spec(_algo_raises_validation)
    executor = ProcessPoolExecutor(max_workers=1, queue_size=1)
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_AlgoValReq(value=1),
            request_id="req-algo-val-pool",
        )
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "runtime"
        assert result.error.traceback is not None
    finally:
        executor.shutdown()
