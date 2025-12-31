from datetime import datetime, timezone

from algo_sdk import (
    AlgorithmContext,
    execution_context,
    get_current_context,
    get_current_request_datetime,
    get_response_meta,
    set_response_code,
    set_response_context,
    set_response_message,
)


def test_response_meta_and_request_datetime_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    ctx = AlgorithmContext(traceId="trace-ctx", tenantId="tenant-1")

    with execution_context(
        request_id="req-1",
        trace_id="trace-ctx",
        request_datetime=now,
        context=ctx,
    ):
        set_response_code(201)
        set_response_message("custom")
        set_response_context({"traceId": "resp-trace"})

        meta = get_response_meta()
        assert meta is not None
        assert meta.code == 201
        assert meta.message == "custom"
        assert meta.context is not None
        assert meta.context.traceId == "resp-trace"
        assert get_current_context() is not None
        assert get_current_request_datetime() == now
