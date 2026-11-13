"""Raw JSON must survive HTTP validation and every executor boundary."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmRequest,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionMode,
    ExecutionRequest,
    InProcessExecutor,
    IsolatedProcessPoolExecutor,
    ProcessPoolExecutor,
    create_app,
    execution_context,
    get_current_raw_data,
)


RAW = {
    "id": "original",
    "force": {"equipment": [{"uuid": "123", "custom_power": 250}]},
    "unknown_config": [None, True, 9007199254740993, "250"],
}


class RawRequest(BaseModel):
    fail: bool = False


class RawResult(BaseModel):
    seen: dict[str, Any] | None
    digest: str


class RawAlgorithm(BaseAlgorithm[RawRequest, RawResult]):
    def run(self, req: RawRequest) -> RawResult:
        raw = get_current_raw_data()
        seen = deepcopy(raw)
        if raw is not None:
            raw.setdefault("mutated", []).append(True)
            if "force" in raw:
                raw["force"]["equipment"][0]["custom_power"] = -1
        if req.fail:
            raise RuntimeError("test raw-data cleanup")
        return RawResult(seen=seen, digest=json_digest(seen))


def json_digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def build_spec() -> AlgorithmSpec:
    return AlgorithmSpec(
        name="raw_echo",
        version="v1",
        description="raw-data roundtrip",
        created_time="2026-11-13",
        author="qa",
        category="unit",
        application_scenarios="test",
        input_model=RawRequest,
        output_model=RawResult,
        algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(
            execution_mode=ExecutionMode.IN_PROCESS,
            max_workers=1,
        ),
        entrypoint=RawAlgorithm,
        is_class=True,
    )


def envelope(**kwargs: Any) -> AlgorithmRequest:
    return AlgorithmRequest(
        requestId="raw-1",
        datetime=datetime.now(timezone.utc),
        data={"fail": False},
        **kwargs,
    )


@pytest.mark.parametrize("value", [RAW, {}, None])
def test_request_accepts_optional_raw_object(value: Any) -> None:
    assert envelope(rawData=value).rawData == value
    assert envelope().rawData is None


@pytest.mark.parametrize("value", [[], [1], "{}", 123, True])
def test_request_rejects_non_object_raw_data(value: Any) -> None:
    with pytest.raises(ValidationError):
        envelope(rawData=value)


def test_nested_context_restores_and_copies_raw_data() -> None:
    original = deepcopy(RAW)
    assert get_current_raw_data() is None
    with execution_context(
        request_id="outer", trace_id=None, context=None, raw_data=original,
    ):
        outer = get_current_raw_data()
        assert outer == RAW
        assert outer is not original
        with pytest.raises(RuntimeError):
            with execution_context(
                request_id="inner", trace_id=None, context=None,
                raw_data={},
            ):
                assert get_current_raw_data() == {}
                raise RuntimeError("cleanup")
        assert get_current_raw_data() is outer
    assert get_current_raw_data() is None
    assert original == RAW


@pytest.mark.parametrize("kind", ["in_process", "shared", "isolated"])
def test_executors_preserve_raw_and_clear_failed_invocations(kind: str) -> None:
    executor = {
        "in_process": InProcessExecutor,
        "shared": lambda: ProcessPoolExecutor(max_workers=1),
        "isolated": lambda: IsolatedProcessPoolExecutor(default_max_workers=1),
    }[kind]()
    spec = build_spec()
    original = deepcopy(RAW)
    try:
        for fail, raw in [(False, original), (True, original), (False, None),
                          (False, {}), (False, original)]:
            result = executor.submit(ExecutionRequest(
                spec=spec, payload={"fail": fail}, request_id="exec-raw",
                raw_data=raw,
            ))
            assert result.success is not fail
            if not fail:
                assert result.data is not None
                assert result.data.seen == raw
            assert get_current_raw_data() is None
            assert original == RAW
        invalid = executor.submit(ExecutionRequest(
            spec=spec, payload={"unknown": True}, request_id="invalid",
            raw_data=original,
        ))
        assert not invalid.success
        assert invalid.error is not None
        assert invalid.error.kind == "validation"
        assert get_current_raw_data() is None
    finally:
        executor.shutdown()


def test_concurrent_invocations_do_not_share_raw_data() -> None:
    executor = InProcessExecutor()
    spec = build_spec()

    def invoke(index: int) -> dict[str, Any] | None:
        result = executor.submit(ExecutionRequest(
            spec=spec, payload={}, request_id=f"concurrent-{index}",
            raw_data={"id": index},
        ))
        assert result.success
        assert result.data is not None
        assert get_current_raw_data() is None
        return result.data.seen

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(invoke, range(20))) == [
                {"id": index} for index in range(20)
            ]
    finally:
        executor.shutdown()


def test_http_reads_raw_data_without_changing_business_input_or_response() -> None:
    registry = AlgorithmRegistry()
    registry.register(build_spec())
    with TestClient(create_app(registry)) as client:
        for raw in [RAW, {}, None]:
            request = envelope(rawData=raw).model_dump(mode="json")
            response = client.post("/algorithms/raw_echo/v1", json=request)
            assert response.status_code == 200
            body = response.json()
            assert body["code"] == 0
            assert body["data"]["digest"] == json_digest(raw)
            # HTTP response normalizes business keys; no raw envelope is echoed.
            assert "rawData" not in body
            assert body["context"] is None
            if raw is None or raw == {}:
                assert body["data"]["seen"] == raw
            else:
                assert body["data"]["seen"]["unknownConfig"] == RAW[
                    "unknown_config"
                ]
        invalid = envelope().model_dump(mode="json")
        invalid["rawData"] = []
        assert client.post("/algorithms/raw_echo/v1", json=invalid).status_code == 422
        schema = client.app.openapi()
        assert "rawData" in schema["components"]["schemas"][
            "AlgorithmRequest"
        ]["properties"]
