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
    InProcessExecutor,
    ObservationHooks,
    set_response_code,
    set_response_context,
    set_response_message,
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


class _MetaAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, req: _Req) -> _Resp:  # type: ignore[override]
        set_response_code(201)
        set_response_message("created")
        set_response_context({"traceId": "resp-trace"})
        return _Resp(doubled=req.value * 2)


class _MetaFailAlgo(BaseAlgorithm[_Req, _Resp]):
    def run(self, _: _Req) -> _Resp:  # type: ignore[override]
        set_response_code(418)
        set_response_message("teapot")
        set_response_context({"traceId": "resp-trace"})
        raise RuntimeError("boom")


def _build_spec(entrypoint: object, *,
                name: str = "demo") -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        version="v1",
        description=None,
        created_time="2026-01-06",
        author="qa",
        category="unit",
        application_scenarios="test",
        extra={"owner": "unit"},
        input_model=_Req,
        output_model=_Resp,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(),
        entrypoint=entrypoint,  # type: ignore[arg-type]
        is_class=True,
    )


def _build_request(
    value: Any, *, request_id: str = "req-1"
) -> AlgorithmRequest:
    return AlgorithmRequest(
        requestId=request_id,
        datetime=datetime.now(timezone.utc),
        context=AlgorithmContext(traceId="trace-1"),
        data=value,
    )


def test_service_invokes_executor_and_wraps_success() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_DoubleAlgo))
    events: list[str] = []

    hooks = ObservationHooks(
        on_start=lambda _: events.append("start"),
        on_complete=lambda _, __: events.append("done"),
    )
    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
        observation=hooks,
    )

    request = _build_request(_Req(value=2))
    response = service.invoke("demo", "v1", request)

    assert response.code == 0
    assert response.data is not None
    assert response.data.doubled == 4
    assert events == ["start", "done"]
    assert response.requestId == request.requestId
    assert response.context is None


def test_service_wraps_runtime_error_and_calls_error_hook() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_FailAlgo, name="fail"))
    events: list[str] = []
    hooks = ObservationHooks(on_error=lambda _, __: events.append("error"))
    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
        observation=hooks,
    )

    request = _build_request(_Req(value=1), request_id="fail-id")
    response = service.invoke("fail", "v1", request)

    assert response.code == 500
    assert response.data is None
    assert response.requestId == "fail-id"
    assert events == ["error"]


def test_service_response_meta_overrides_success() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_MetaAlgo, name="meta"))
    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
    )

    request = _build_request(_Req(value=3))
    response = service.invoke("meta", "v1", request)

    assert response.code == 201
    assert response.message == "created"
    assert response.context is not None
    assert response.context.traceId == "resp-trace"
    assert response.data is not None
    assert response.data.doubled == 6


def test_service_response_meta_overrides_error() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_MetaFailAlgo, name="meta-fail"))
    service = AlgorithmHttpService(
        registry,
        executor=InProcessExecutor(),
    )

    request = _build_request(_Req(value=1))
    response = service.invoke("meta-fail", "v1", request)

    assert response.code == 418
    assert response.message == "teapot"
    assert response.context is not None
    assert response.context.traceId == "resp-trace"
    assert response.data is None
