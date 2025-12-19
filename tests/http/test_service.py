from datetime import datetime, timezone
from typing import Any

from algo_sdk.core import (
    AlgorithmRegistry,
    AlgorithmSpec,
    BaseModel,
    ExecutionConfig,
    InProcessExecutor,
)
from algo_sdk.http import AlgorithmHttpService, ObservationHooks
from algo_sdk.protocol.models import AlgorithmContext, AlgorithmRequest


class _Req(BaseModel):
    value: int


class _Resp(BaseModel):
    doubled: int


def _double(req: _Req) -> _Resp:
    return _Resp(doubled=req.value * 2)


def _fail(_: _Req) -> _Resp:
    raise RuntimeError("boom")


def _build_spec(entrypoint: object, *,
                name: str = "demo") -> AlgorithmSpec:
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
    registry.register(_build_spec(_double))
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
    assert response.context.traceId == "trace-1"


def test_service_wraps_runtime_error_and_calls_error_hook() -> None:
    registry = AlgorithmRegistry()
    registry.register(_build_spec(_fail, name="fail"))
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
