from datetime import datetime, timezone
from typing import Any

from algo_sdk.core import (
    AlgorithmRegistry,
    AlgorithmSpec,
    BaseModel,
    ExecutionConfig,
    InProcessExecutor,
)
from algo_sdk.http import AlgorithmHttpService
from algo_sdk.observability import (
    InMemoryMetrics,
    InMemoryTracer,
    create_observation_hooks,
)
from algo_sdk.protocol.models import AlgorithmContext, AlgorithmRequest


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def _double(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)


def _fail(_: _Req) -> _Resp:
    raise RuntimeError("boom")


def _build_spec(entrypoint: object, *, name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_Resp,
        execution=ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=False,
    )


def _build_request(
    value: Any, *, request_id: str
) -> AlgorithmRequest:
    return AlgorithmRequest(
        requestId=request_id,
        datetime=datetime.now(timezone.utc),
        context=AlgorithmContext(traceId="trace-1"),
        data=value,
    )


def test_metrics_and_tracing_capture_execution() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_double, name="demo"))
    registry.register(_build_spec(_fail, name="fail"))

    metrics = InMemoryMetrics()
    tracer = InMemoryTracer()
    hooks = create_observation_hooks(metrics, tracer)

    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
        observation=hooks,
    )

    service.invoke("demo", "v1", _build_request(_Req(value=2),
                                                request_id="req-1"))
    service.invoke("fail", "v1", _build_request(_Req(value=1),
                                                request_id="req-2"))

    snapshot = metrics.snapshot()
    demo_metrics = snapshot[("demo", "v1")]
    fail_metrics = snapshot[("fail", "v1")]

    assert demo_metrics.requests_total == 1
    assert demo_metrics.requests_failed == 0
    assert demo_metrics.inflight == 0
    assert demo_metrics.latency_ms.total_count == 1
    assert demo_metrics.queue_wait_ms.total_count == 1

    assert fail_metrics.requests_total == 1
    assert fail_metrics.requests_failed == 1
    assert fail_metrics.inflight == 0
    assert fail_metrics.latency_ms.total_count == 1
    assert fail_metrics.queue_wait_ms.total_count == 1

    spans = tracer.spans()
    status_map = {span.request_id: span.status for span in spans}
    assert status_map["req-1"] == "success"
    assert status_map["req-2"] == "error"
