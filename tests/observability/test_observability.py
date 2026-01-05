from datetime import datetime, timezone
from typing import Any

from algo_sdk import (
    AlgorithmContext,
    AlgorithmHttpService,
    AlgorithmRegistry,
    AlgorithmRequest,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    InMemoryMetrics,
    InMemoryTracer,
    InProcessExecutor,
    create_observation_hooks,
)


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


class _DoubleAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        return _Resp(doubled=req.value * 2)


class _FailAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, _: _Req) -> _Resp:  # type: ignore[override]
        raise RuntimeError("boom")


def _build_spec(entrypoint: object, *, name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        version="v1",
        description=None,
        input_model=_Req,
        output_model=_Resp,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=True,
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
    registry.register(_build_spec(_DoubleAlgo, name="demo"))
    registry.register(_build_spec(_FailAlgo, name="fail"))

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


def test_metrics_exports_prometheus_and_otel() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_DoubleAlgo, name="demo"))

    metrics = InMemoryMetrics()
    hooks = create_observation_hooks(metrics)
    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
        observation=hooks,
    )

    service.invoke("demo", "v1", _build_request(_Req(value=3),
                                                request_id="req-3"))

    text = metrics.render_prometheus_text()
    assert "algo_sdk_requests_total" in text
    assert "algo_sdk_request_latency_ms_bucket" in text

    otel_payload = metrics.build_otel_metrics()
    assert "resourceMetrics" in otel_payload
