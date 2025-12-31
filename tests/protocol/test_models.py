from datetime import datetime, timezone

import pytest

from algo_sdk import (
    AlgorithmContext,
    AlgorithmRequest,
    AlgorithmResponse,
    api_error,
    api_success,
)


def test_algorithm_request_requires_request_id() -> None:
    with pytest.raises(ValueError):
        AlgorithmRequest(requestId="", datetime=datetime.now(timezone.utc), data={})


def test_algorithm_response_success_helper() -> None:
    resp = api_success(data={"ok": True}, request_id="req-1")
    assert resp.code == 0
    assert resp.message == "success"
    assert resp.requestId == "req-1"


def test_algorithm_response_error_helper() -> None:
    ctx = AlgorithmContext(traceId="t1")
    resp = api_error("boom", code=500, request_id="req-2", context=ctx)
    assert resp.code == 500
    assert resp.message == "boom"
    assert resp.context.traceId == "t1"
