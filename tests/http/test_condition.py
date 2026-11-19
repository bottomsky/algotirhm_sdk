from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import algo_core_service.algorithms as algorithms
from algo_dto.condition import ConditionRequest, ConditionResult
from algo_sdk import (
    AlgorithmRegistry,
    ExecutionConfig,
    ExecutionMode,
    create_app,
)
from algo_sdk.core import AlgorithmType


@pytest.fixture
def condition_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("SERVICE_REGISTRY_ENABLED", "false")
    registry = AlgorithmRegistry()
    registry.register_from_module(algorithms)
    spec = registry.get("Condition", "v1")
    assert spec.algorithm_type is AlgorithmType.CONDITION
    assert spec.execution.execution_mode is ExecutionMode.IN_PROCESS
    assert spec.input_model is ConditionRequest
    assert spec.output_model is ConditionResult
    with TestClient(create_app(registry)) as client:
        yield client


def test_condition_catalog_and_schema(condition_client: TestClient) -> None:
    response = condition_client.get("/algorithms")
    assert response.status_code == 200
    entry = next(
        item
        for item in response.json()["data"]
        if item["name"] == "Condition" and item["version"] == "v1"
    )
    assert entry["algorithmType"] == "Condition"
    assert entry["category"] == "BehaviorTree"

    response = condition_client.get("/algorithms/Condition/v1/schema")
    assert response.status_code == 200
    schema = response.json()["data"]
    assert schema["output"]["type"] == "boolean"
    assert set(schema["input"]["required"]) == {
        "frameData",
        "projectDto",
        "forceType",
    }
    assert schema["input"]["properties"]["satId"]["type"] == "string"
    definitions = schema["input"]["$defs"]
    assert "ProjectDTO" in definitions
    assert "PlatParam" in definitions
    assert "LaserPayloadParam" in definitions
    assert definitions["ProjectDTO"]["additionalProperties"] is True
    assert "algorithmsSatType" in definitions["PlatParam"]["properties"]


@pytest.mark.parametrize("mode", ["in_process", "shared", "isolated"])
def test_full_csharp_models_run_in_all_execution_modes(mode: str) -> None:
    source = Path(__file__).resolve().parents[1]
    data = json.loads(
        (source / "fixtures/csharp_condition_contract.json").read_text()
    )["conditionData"]
    catalog = AlgorithmRegistry()
    catalog.register_from_module(algorithms)
    spec = replace(catalog.get("Condition", "v1"), execution=ExecutionConfig(
        execution_mode=(ExecutionMode.IN_PROCESS if mode == "in_process"
                        else ExecutionMode.PROCESS_POOL),
        isolated_pool=mode == "isolated", max_workers=1,
    ))
    registry = AlgorithmRegistry()
    registry.register(spec)
    with TestClient(create_app(registry)) as client:
        response = client.post("/algorithms/Condition/v1", json={
            "requestId": "csharp-full", "datetime": "2026-11-13T10:00:00Z",
            "data": data,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0, body
        assert body["data"] is True


@pytest.mark.parametrize("fault, expected", [(1, True), (0, False)])
def test_condition_http_boolean(
    condition_client: TestClient, fault: int, expected: bool
) -> None:
    response = condition_client.post(
        "/algorithms/Condition/v1",
        json={
            "requestId": "condition-demo-001",
            "datetime": "2026-11-13T15:00:00+08:00",
            "context": {},
            "data": {
                "frameData": {
                    "data": {"1001": {"forceType": 1, "isSatFault": fault}}
                },
                "projectDto": {},
                "forceType": 1,
                "satId": "1001",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["requestId"] == "condition-demo-001"
    assert payload["data"] is expected


@pytest.mark.parametrize(
    "invalid_state",
    [{"forceType": 1}, {"forceType": 1, "isSatFault": "invalid"}],
)
def test_condition_http_validation(
    condition_client: TestClient, invalid_state: dict[str, object]
) -> None:
    response = condition_client.post(
        "/algorithms/Condition/v1",
        json={
            "requestId": "condition-invalid",
            "datetime": "2026-11-13T15:00:00+08:00",
            "data": {
                "frameData": {"data": {"1001": invalid_state}},
                "projectDto": {},
                "forceType": 1,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert payload["data"] is None


def test_condition_requires_standard_envelope(
    condition_client: TestClient,
) -> None:
    response = condition_client.post(
        "/algorithms/Condition/v1",
        json={"frameData": {"data": {}}, "projectDto": {}, "forceType": 1},
    )
    assert response.status_code == 422
