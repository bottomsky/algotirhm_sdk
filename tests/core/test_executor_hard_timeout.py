import os
import threading
import time
import uuid

from algo_sdk import (
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionRequest,
    ProcessPoolExecutor,
)


class _DoubleReq(BaseModel):
    value: int


class _DoubleResp(BaseModel):
    doubled: int


class _DoubleAlgo(BaseAlgorithm[_DoubleReq, _DoubleResp]):
    def run(self, req: _DoubleReq) -> _DoubleResp:  # type: ignore[override]
        return _DoubleResp(doubled=req.value * 2)


class _SleepReq(BaseModel):
    delay_s: float


class _SleepResp(BaseModel):
    done: bool


class _SleepAlgo(BaseAlgorithm[_SleepReq, _SleepResp]):
    def run(self, req: _SleepReq) -> _SleepResp:  # type: ignore[override]
        time.sleep(req.delay_s)
        return _SleepResp(done=True)


class _CrashReq(BaseModel):
    code: int = 1


class _CrashResp(BaseModel):
    ok: bool


class _CrashAlgo(BaseAlgorithm[_CrashReq, _CrashResp]):
    def run(self, req: _CrashReq) -> _CrashResp:  # type: ignore[override]
        os._exit(req.code)


class _StateReq(BaseModel):
    value: int


class _StateResp(BaseModel):
    instance_id: str


class _StatefulAlgo(BaseAlgorithm[_StateReq, _StateResp]):
    def __init__(self) -> None:
        self._instance_id = uuid.uuid4().hex

    def run(self, req: _StateReq) -> _StateResp:  # type: ignore[override]
        return _StateResp(instance_id=self._instance_id)


def _build_spec(
    *,
    name: str,
    entrypoint: object,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    execution: ExecutionConfig | None = None,
    is_class: bool,
) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        version="v1",
        description=None,
        input_model=input_model,
        output_model=output_model,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=execution or ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=is_class,
    )


def _warm_up(executor: ProcessPoolExecutor) -> None:
    spec = _build_spec(
        name="warmup",
        entrypoint=_DoubleAlgo,
        input_model=_DoubleReq,
        output_model=_DoubleResp,
        is_class=True,
    )
    req = ExecutionRequest(
        spec=spec, payload=_DoubleReq(value=1), request_id="warmup"
    )
    result = executor.submit(req)
    assert result.success is True


def test_hard_timeout_kills_and_restarts_worker_pid_changes() -> None:
    sleep_spec = _build_spec(
        name="sleep",
        entrypoint=_SleepAlgo,
        input_model=_SleepReq,
        output_model=_SleepResp,
        execution=ExecutionConfig(timeout_s=10),
        is_class=True,
    )
    double_spec = _build_spec(
        name="double",
        entrypoint=_DoubleAlgo,
        input_model=_DoubleReq,
        output_model=_DoubleResp,
        is_class=True,
    )

    executor = ProcessPoolExecutor(
        max_workers=1, queue_size=2, poll_interval_s=0.02
    )
    try:
        executor.start()
        _warm_up(executor)

        timeout_req = ExecutionRequest(
            spec=sleep_spec,
            payload=_SleepReq(delay_s=2.0),
            request_id="req-timeout",
            timeout_s=0.2,
        )
        r1 = executor.submit(timeout_req)
        assert r1.success is False
        assert r1.error is not None
        assert r1.error.kind == "timeout"
        assert r1.worker_pid is not None
        killed_pid = r1.worker_pid

        r2 = executor.submit(
            ExecutionRequest(
                spec=double_spec,
                payload=_DoubleReq(value=3),
                request_id="req-after-timeout",
                timeout_s=2,
            )
        )
        assert r2.success is True
        assert r2.data is not None
        assert r2.data.doubled == 6
        assert r2.worker_pid is not None
        assert r2.worker_pid != killed_pid
    finally:
        executor.shutdown()


def test_timeout_before_execution_started_does_not_kill_busy_worker() -> None:
    sleep_spec = _build_spec(
        name="sleep2",
        entrypoint=_SleepAlgo,
        input_model=_SleepReq,
        output_model=_SleepResp,
        execution=ExecutionConfig(timeout_s=10),
        is_class=True,
    )

    executor = ProcessPoolExecutor(
        max_workers=1, queue_size=2, poll_interval_s=0.02
    )
    try:
        executor.start()
        _warm_up(executor)

        result_holder: dict[str, object] = {}

        def _run_long() -> None:
            req = ExecutionRequest(
                spec=sleep_spec,
                payload=_SleepReq(delay_s=0.8),
                request_id="req-long",
                timeout_s=5,
            )
            result_holder["r"] = executor.submit(req)

        t = threading.Thread(target=_run_long, daemon=True)
        t.start()
        time.sleep(0.1)

        short_req = ExecutionRequest(
            spec=sleep_spec,
            payload=_SleepReq(delay_s=0.01),
            request_id="req-queue-timeout",
            timeout_s=0.15,
        )
        r2 = executor.submit(short_req)
        assert r2.success is False
        assert r2.error is not None
        assert r2.error.kind == "timeout"
        assert "before execution started" in r2.error.message

        t.join(timeout=3.0)
        assert "r" in result_holder
        r1 = result_holder["r"]
        assert hasattr(r1, "success")
        assert r1.success is True  # type: ignore[attr-defined]
    finally:
        executor.shutdown()


def test_worker_crash_is_reported_and_pool_recovers() -> None:
    crash_spec = _build_spec(
        name="crash",
        entrypoint=_CrashAlgo,
        input_model=_CrashReq,
        output_model=_CrashResp,
        is_class=True,
    )
    double_spec = _build_spec(
        name="double2",
        entrypoint=_DoubleAlgo,
        input_model=_DoubleReq,
        output_model=_DoubleResp,
        is_class=True,
    )

    executor = ProcessPoolExecutor(
        max_workers=1, queue_size=2, poll_interval_s=0.02
    )
    try:
        executor.start()
        _warm_up(executor)

        r1 = executor.submit(
            ExecutionRequest(
                spec=crash_spec,
                payload=_CrashReq(code=1),
                request_id="req-crash",
                timeout_s=2,
            )
        )
        assert r1.success is False
        assert r1.error is not None
        assert r1.error.kind == "system"

        r2 = executor.submit(
            ExecutionRequest(
                spec=double_spec,
                payload=_DoubleReq(value=5),
                request_id="req-after-crash",
                timeout_s=2,
            )
        )
        assert r2.success is True
        assert r2.data is not None
        assert r2.data.doubled == 10
    finally:
        executor.shutdown()


def test_queue_full_is_rejected_under_concurrency() -> None:
    sleep_spec = _build_spec(
        name="sleep3",
        entrypoint=_SleepAlgo,
        input_model=_SleepReq,
        output_model=_SleepResp,
        execution=ExecutionConfig(timeout_s=10),
        is_class=True,
    )

    executor = ProcessPoolExecutor(
        max_workers=1, queue_size=1, poll_interval_s=0.02
    )
    try:
        executor.start()
        _warm_up(executor)

        barrier = threading.Barrier(2)
        results: list[object] = []
        lock = threading.Lock()

        def _submit_long(i: int) -> None:
            barrier.wait(timeout=2.0)
            r = executor.submit(
                ExecutionRequest(
                    spec=sleep_spec,
                    payload=_SleepReq(delay_s=0.6),
                    request_id=f"req-conc-{i}",
                    timeout_s=2,
                )
            )
            with lock:
                results.append(r)

        t1 = threading.Thread(target=_submit_long, args=(1,), daemon=True)
        t2 = threading.Thread(target=_submit_long, args=(2,), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert len(results) == 2
        kinds = [
            (
                r.error.kind
                if (not r.success and r.error is not None)
                else "success"
            )
            for r in results
        ]
        assert "rejected" in kinds
    finally:
        executor.shutdown()


def test_stateful_algo_persists_until_worker_killed_then_resets() -> None:
    stateful_spec = _build_spec(
        name="stateful",
        entrypoint=_StatefulAlgo,
        input_model=_StateReq,
        output_model=_StateResp,
        execution=ExecutionConfig(stateful=True, timeout_s=10),
        is_class=True,
    )
    sleeper_spec = _build_spec(
        name="sleep4",
        entrypoint=_SleepAlgo,
        input_model=_SleepReq,
        output_model=_SleepResp,
        execution=ExecutionConfig(timeout_s=10),
        is_class=True,
    )

    executor = ProcessPoolExecutor(
        max_workers=1, queue_size=2, poll_interval_s=0.02
    )
    try:
        executor.start()
        _warm_up(executor)

        r1 = executor.submit(
            ExecutionRequest(
                spec=stateful_spec,
                payload=_StateReq(value=1),
                request_id="req-state-1",
                timeout_s=2,
            )
        )
        assert r1.success is True
        assert r1.data is not None
        id1 = r1.data.instance_id

        r2 = executor.submit(
            ExecutionRequest(
                spec=stateful_spec,
                payload=_StateReq(value=2),
                request_id="req-state-2",
                timeout_s=2,
            )
        )
        assert r2.success is True
        assert r2.data is not None
        assert r2.data.instance_id == id1

        r3 = executor.submit(
            ExecutionRequest(
                spec=sleeper_spec,
                payload=_SleepReq(delay_s=2.0),
                request_id="req-state-timeout",
                timeout_s=0.2,
            )
        )
        assert r3.success is False
        assert r3.error is not None
        assert r3.error.kind == "timeout"

        r4 = executor.submit(
            ExecutionRequest(
                spec=stateful_spec,
                payload=_StateReq(value=3),
                request_id="req-state-3",
                timeout_s=2,
            )
        )
        assert r4.success is True
        assert r4.data is not None
        assert r4.data.instance_id != id1
    finally:
        executor.shutdown()
