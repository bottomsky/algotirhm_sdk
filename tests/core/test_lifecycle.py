from __future__ import annotations

import time

from algo_sdk.core import (
    AlgorithmSpec,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionRequest,
    InProcessExecutor,
    ProcessPoolExecutor,
)


class _Req(BaseModel):
    value: int


class _LifecycleResp(BaseModel):
    pid: int
    instance_seq: int
    init_calls: int
    run_calls: int
    after_run_calls: int
    shutdown_calls: int
    after_run_called: bool
    shutdown_called: bool


_INSTANCE_SEQ = 0


def _next_instance_seq() -> int:
    global _INSTANCE_SEQ
    _INSTANCE_SEQ += 1
    return _INSTANCE_SEQ


_FAILURE_AFTER_RUN_TOTAL = 0
_FAILURE_SHUTDOWN_TOTAL = 0


class _LifecycleAlgo(BaseAlgorithm[_Req, _LifecycleResp]):
    def __init__(self) -> None:
        self._seq = _next_instance_seq()
        self._init_calls = 0
        self._run_calls = 0
        self._after_run_calls = 0
        self._shutdown_calls = 0
        self._envelope: dict[str, object] | None = None

    def initialize(self) -> None:
        self._init_calls += 1

    def run(self, req: _Req) -> dict[str, object]:  # type: ignore[override]
        self._run_calls += 1
        envelope: dict[str, object] = {
            "pid": __import__("os").getpid(),
            "instance_seq": self._seq,
            "init_calls": self._init_calls,
            "run_calls": self._run_calls,
            "after_run_calls": self._after_run_calls,
            "shutdown_calls": self._shutdown_calls,
            "after_run_called": False,
            "shutdown_called": False,
        }
        self._envelope = envelope
        _ = req
        return envelope

    def after_run(self) -> None:
        self._after_run_calls += 1
        if self._envelope is not None:
            self._envelope["after_run_calls"] = self._after_run_calls
            self._envelope["after_run_called"] = True

    def shutdown(self) -> None:
        self._shutdown_calls += 1
        if self._envelope is not None:
            self._envelope["shutdown_calls"] = self._shutdown_calls
            self._envelope["shutdown_called"] = True


class _FailingLifecycleAlgo(BaseAlgorithm[_Req, _LifecycleResp]):
    def __init__(self) -> None:
        self._seq = _next_instance_seq()

    def run(self, req: _Req) -> _LifecycleResp:  # type: ignore[override]
        _ = req
        raise RuntimeError("boom")

    def after_run(self) -> None:
        global _FAILURE_AFTER_RUN_TOTAL
        _FAILURE_AFTER_RUN_TOTAL += 1

    def shutdown(self) -> None:
        global _FAILURE_SHUTDOWN_TOTAL
        _FAILURE_SHUTDOWN_TOTAL += 1


def _build_spec(*, stateful: bool, entrypoint: object, name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_LifecycleResp,
        execution=ExecutionConfig(stateful=stateful),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=True,
    )


def test_inprocess_stateless_calls_initialize_after_run_shutdown() -> None:
    spec = _build_spec(stateful=False, entrypoint=_LifecycleAlgo, name="life")
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="r1")
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.init_calls == 1
        assert result.data.run_calls == 1
        assert result.data.after_run_calls == 1
        assert result.data.shutdown_calls == 1
        assert result.data.after_run_called is True
        assert result.data.shutdown_called is True
    finally:
        executor.shutdown()


def test_inprocess_stateful_calls_initialize_once_and_after_run_each_time() -> None:
    spec = _build_spec(stateful=True, entrypoint=_LifecycleAlgo, name="life-s")
    executor = InProcessExecutor()
    try:
        req1 = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="r1")
        req2 = ExecutionRequest(spec=spec, payload=_Req(value=2), request_id="r2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None

        assert res1.data.instance_seq == res2.data.instance_seq
        assert res1.data.init_calls == 1
        assert res2.data.init_calls == 1

        assert res1.data.run_calls == 1
        assert res2.data.run_calls == 2

        assert res1.data.after_run_calls == 1
        assert res2.data.after_run_calls == 2

        assert res1.data.shutdown_calls == 0
        assert res2.data.shutdown_calls == 0
        assert res1.data.shutdown_called is False
        assert res2.data.shutdown_called is False
    finally:
        executor.shutdown()


def test_process_pool_stateless_calls_initialize_after_run_shutdown() -> None:
    spec = _build_spec(stateful=False, entrypoint=_LifecycleAlgo, name="pool-life")
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        req = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="p1")
        result = executor.submit(req)
        assert result.success is True
        assert result.data is not None
        assert result.data.init_calls == 1
        assert result.data.run_calls == 1
        assert result.data.after_run_calls == 1
        assert result.data.shutdown_calls == 1
        assert result.data.after_run_called is True
        assert result.data.shutdown_called is True
    finally:
        executor.shutdown()


def test_process_pool_stateful_calls_initialize_once_and_after_run_each_time() -> None:
    spec = _build_spec(stateful=True, entrypoint=_LifecycleAlgo, name="pool-life-s")
    executor = ProcessPoolExecutor(max_workers=1, queue_size=2)
    try:
        req1 = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="p1")
        req2 = ExecutionRequest(spec=spec, payload=_Req(value=2), request_id="p2")
        res1 = executor.submit(req1)
        res2 = executor.submit(req2)
        assert res1.success is True
        assert res2.success is True
        assert res1.data is not None
        assert res2.data is not None

        assert res1.data.instance_seq == res2.data.instance_seq
        assert res1.data.init_calls == 1
        assert res2.data.init_calls == 1
        assert res1.data.run_calls == 1
        assert res2.data.run_calls == 2
        assert res1.data.after_run_calls == 1
        assert res2.data.after_run_calls == 2

        assert res1.data.shutdown_calls == 0
        assert res2.data.shutdown_calls == 0
        assert res1.data.shutdown_called is False
        assert res2.data.shutdown_called is False
    finally:
        executor.shutdown()


def test_inprocess_failure_skips_after_run_but_calls_shutdown_for_stateless() -> None:
    global _FAILURE_AFTER_RUN_TOTAL
    global _FAILURE_SHUTDOWN_TOTAL
    _FAILURE_AFTER_RUN_TOTAL = 0
    _FAILURE_SHUTDOWN_TOTAL = 0

    spec = _build_spec(stateful=False, entrypoint=_FailingLifecycleAlgo, name="fail")
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="f1")
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "runtime"
        assert _FAILURE_AFTER_RUN_TOTAL == 0
        assert _FAILURE_SHUTDOWN_TOTAL == 1
    finally:
        executor.shutdown()


def test_inprocess_failure_skips_after_run_and_shutdown_until_executor_shutdown_for_stateful() -> None:
    global _FAILURE_AFTER_RUN_TOTAL
    global _FAILURE_SHUTDOWN_TOTAL
    _FAILURE_AFTER_RUN_TOTAL = 0
    _FAILURE_SHUTDOWN_TOTAL = 0

    spec = _build_spec(stateful=True, entrypoint=_FailingLifecycleAlgo, name="fail-s")
    executor = InProcessExecutor()
    try:
        req = ExecutionRequest(spec=spec, payload=_Req(value=1), request_id="f2")
        result = executor.submit(req)
        assert result.success is False
        assert result.error is not None
        assert result.error.kind == "runtime"
        assert _FAILURE_AFTER_RUN_TOTAL == 0
        assert _FAILURE_SHUTDOWN_TOTAL == 0
    finally:
        executor.shutdown()

    assert _FAILURE_AFTER_RUN_TOTAL == 0
    assert _FAILURE_SHUTDOWN_TOTAL == 1


class _ShutdownProbeReq(BaseModel):
    file_path: str


class _ShutdownProbeResp(BaseModel):
    ok: bool


class _ShutdownProbeAlgo(BaseAlgorithm[_ShutdownProbeReq, _ShutdownProbeResp]):
    def __init__(self) -> None:
        self._file_path: str | None = None

    def run(self, req: _ShutdownProbeReq) -> _ShutdownProbeResp:  # type: ignore[override]
        self._file_path = req.file_path
        return _ShutdownProbeResp(ok=True)

    def shutdown(self) -> None:
        if self._file_path is None:
            return
        # 通过文件副作用在父进程可观测 shutdown 被调用。
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write("shutdown\n")


def test_process_pool_stateful_calls_shutdown_on_worker_exit(tmp_path) -> None:
    marker = tmp_path / "shutdown.txt"
    spec = AlgorithmSpec(
        name="shutdown-probe",
        version="v1",
        description=None,
        input_model=_ShutdownProbeReq,
        output_model=_ShutdownProbeResp,
        execution=ExecutionConfig(stateful=True),
        entrypoint=_ShutdownProbeAlgo,
        is_class=True,
    )

    executor = ProcessPoolExecutor(max_workers=1, queue_size=1, kill_grace_s=1.0)
    try:
        req = ExecutionRequest(
            spec=spec,
            payload=_ShutdownProbeReq(file_path=str(marker)),
            request_id="probe-1",
        )
        result = executor.submit(req)
        assert result.success is True
    finally:
        executor.shutdown(wait=True)

    deadline = time.monotonic() + 3.0
    content = ""
    while time.monotonic() < deadline:
        if marker.exists():
            content = marker.read_text(encoding="utf-8")
            if "shutdown" in content:
                break
        time.sleep(0.05)

    assert "shutdown" in content
