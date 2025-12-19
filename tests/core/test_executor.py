import os
import time

from algo_sdk.core import (
    AlgorithmSpec,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionMode,
    ExecutionRequest,
    DispatchingExecutor,
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


class _DoubleAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


class _SleepReq(BaseModel):
    delay: float


class _SleepResp(BaseModel):
    done: bool


class _SleepAlgo(BaseAlgorithm[_SleepReq, _SleepResp]):
    def run(self, req: _SleepReq) -> _SleepResp:  # type: ignore[override]
        time.sleep(req.delay)
        return _SleepResp(done=True)


class _CtxReq(BaseModel):
    value: int


class _CtxResp(BaseModel):
    trace_id: str | None
    request_id: str | None
    tenant_id: str | None


class _EchoContextAlgo(BaseAlgorithm[_CtxReq, _CtxResp]):
    def run(self, _: _CtxReq) -> _CtxResp:  # type: ignore[override]
        context = get_current_context()
        return _CtxResp(
            trace_id=get_current_trace_id(),
            request_id=get_current_request_id(),
            tenant_id=context.tenantId if context is not None else None,
        )


def _build_double_spec(
    *,
    execution: ExecutionConfig | None = None,
) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="double",
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_Resp,
        execution=execution or ExecutionConfig(),
        entrypoint=_DoubleAlgo,
        is_class=True,
    )


def _build_sleep_spec(
    *,
    execution: ExecutionConfig | None = None,
) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="sleep",
        version="v1",
        description=None,
        input_model=_SleepReq,
        output_model=_SleepResp,
        execution=execution or ExecutionConfig(),
        entrypoint=_SleepAlgo,
        is_class=True,
    )


def _build_ctx_spec() -> AlgorithmSpec:
    return AlgorithmSpec(
        name="ctx",
        version="v1",
        description=None,
        input_model=_CtxReq,
        output_model=_CtxResp,
        execution=ExecutionConfig(),
        entrypoint=_EchoContextAlgo,
        is_class=True,
    )


class _CounterReq(BaseModel):
    value: int


class _CounterResp(BaseModel):
    count: int


class _CounterAlgo(BaseAlgorithm[_CounterReq, _CounterResp]):
    def initialize(self) -> None:
        self._count = 0

    def run(self, req: _CounterReq) -> _CounterResp:  # type: ignore[override]
        self._count += 1
        return _CounterResp(count=self._count)


def _build_counter_spec(*, stateful: bool) -> AlgorithmSpec:
    return AlgorithmSpec(
        name="counter",
        version="v1",
        description=None,
        input_model=_CounterReq,
        output_model=_CounterResp,
        execution=ExecutionConfig(stateful=stateful),
        entrypoint=_CounterAlgo,
        is_class=True,
    )


def test_process_pool_executes_function() -> None:
    spec = _build_double_spec()
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
    spec = _build_sleep_spec(execution=ExecutionConfig(timeout_s=1))
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


def test_process_pool_uses_spec_timeout_by_default() -> None:
    spec = _build_sleep_spec(execution=ExecutionConfig(timeout_s=1))
    executor = ProcessPoolExecutor(max_workers=1, queue_size=1)
    try:
        req = ExecutionRequest(spec=spec,
                               payload=_SleepReq(delay=1.5),
                               request_id="req-timeout-spec")
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "timeout"
    finally:
        executor.shutdown()


def test_process_pool_recovers_after_timeout() -> None:
    slow_spec = _build_sleep_spec(execution=ExecutionConfig(timeout_s=1))
    fast_spec = _build_double_spec()
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        slow_req = ExecutionRequest(spec=slow_spec,
                                    payload=_SleepReq(delay=0.2),
                                    request_id="req-timeout-recover",
                                    timeout_s=0.05)
        slow_result = executor.submit(slow_req)
        assert slow_result.success is False
        assert slow_result.error is not None
        assert slow_result.error.kind == "timeout"

        fast_req = ExecutionRequest(spec=fast_spec,
                                    payload=_Req(value=4),
                                    request_id="req-after-timeout")
        fast_result = executor.submit(fast_req)
        assert fast_result.success is True
        assert fast_result.data is not None
        assert fast_result.data.doubled == 8
    finally:
        executor.shutdown()


def test_dispatching_executor_routes_in_process() -> None:
    spec = _build_double_spec(
        execution=ExecutionConfig(execution_mode=ExecutionMode.IN_PROCESS)
    )
    executor = DispatchingExecutor(global_max_workers=1, global_queue_size=1)
    try:
        req = ExecutionRequest(spec=spec,
                               payload=_Req(value=5),
                               request_id="req-inproc-dispatch")
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.doubled == 10
        assert result.worker_pid == os.getpid()
    finally:
        executor.shutdown()


def test_in_process_propagates_context() -> None:
    spec = _build_ctx_spec()
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
    spec = _build_ctx_spec()
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


def test_inprocess_stateless_creates_instance_per_request() -> None:
    spec = _build_counter_spec(stateful=False)
    executor = InProcessExecutor()
    try:
        req1 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="counter-1")
        req2 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="counter-2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None
        assert res1.data.count == 1
        assert res2.data.count == 1
    finally:
        executor.shutdown()


def test_inprocess_stateful_reuses_instance() -> None:
    spec = _build_counter_spec(stateful=True)
    executor = InProcessExecutor()
    try:
        req1 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="counter-s-1")
        req2 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="counter-s-2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None
        assert res1.data.count == 1
        assert res2.data.count == 2
    finally:
        executor.shutdown()


def test_process_pool_stateless_creates_instance_per_request() -> None:
    spec = _build_counter_spec(stateful=False)
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        req1 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="pool-counter-1")
        req2 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="pool-counter-2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None
        assert res1.data.count == 1
        assert res2.data.count == 1
    finally:
        executor.shutdown()


def test_process_pool_stateful_reuses_instance() -> None:
    spec = _build_counter_spec(stateful=True)
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        req1 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="pool-counter-s-1")
        req2 = ExecutionRequest(spec=spec,
                                payload=_CounterReq(value=1),
                                request_id="pool-counter-s-2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None
        assert res1.data.count == 1
        assert res2.data.count == 2
    finally:
        executor.shutdown()


class _AlgoValReq(BaseModel):
    value: int


class _AlgoValResp(BaseModel):
    ok: bool


class _AlgoRaisesValidationAlgo(BaseAlgorithm[_AlgoValReq, _AlgoValResp]):
    def run(self, _: _AlgoValReq) -> _AlgoValResp:  # type: ignore[override]
        _AlgoValReq.model_validate({"value": "not-an-int"})
        return _AlgoValResp(ok=True)


def _build_val_spec() -> AlgorithmSpec:
    return AlgorithmSpec(
        name="algo-val",
        version="v1",
        description=None,
        input_model=_AlgoValReq,
        output_model=_AlgoValResp,
        execution=ExecutionConfig(),
        entrypoint=_AlgoRaisesValidationAlgo,
        is_class=True,
    )


def test_in_process_algorithm_validation_error_is_runtime() -> None:
    spec = _build_val_spec()
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
    spec = _build_val_spec()
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
