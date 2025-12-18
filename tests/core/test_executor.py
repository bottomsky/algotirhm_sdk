import time

from algo_sdk.core import (
    AlgorithmSpec,
    BaseModel,
    ExecutionConfig,
    ExecutionRequest,
    ProcessPoolExecutor,
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
