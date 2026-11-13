"""Run against an actual C# HTTP-body capture via RAW_DATA_CAPTURE_PATH."""

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from algo_dto.dto import PredictionRequest
from algo_sdk import (
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    BaseModel,
    ExecutionConfig,
    ExecutionMode,
    create_app,
    get_current_raw_data,
)


class InteropResult(BaseModel):
    digest: str
    satellite_id: int
    custom_power: int


class InteropAlgorithm(BaseAlgorithm[PredictionRequest, InteropResult]):
    def run(self, req: PredictionRequest) -> InteropResult:
        raw = get_current_raw_data()
        assert raw is not None
        assert raw["id"] == 17
        assert raw["unknown_config"]["huge"] == 123456789012345678901234567890
        satellite = next(
            item for item in raw["force"]["equipment"]
            if int(item["uuid"]) == req.sat_states.sat_id
        )
        platform = satellite["equipmentParam"]["platParam"]
        assert platform["satMass"] == "100"
        assert satellite["equipmentParam"]["payloadParams"][0][
            "newPayloadParam"
        ]["values"] == [None, "250", False]
        return InteropResult(
            digest=sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
            satellite_id=req.sat_states.sat_id,
            custom_power=platform["customPower"],
        )


@pytest.mark.skipif(
    not os.getenv("RAW_DATA_CAPTURE_PATH"),
    reason="Set RAW_DATA_CAPTURE_PATH to the C# prediction HTTP capture",
)
@pytest.mark.parametrize("kind", ["in_process", "shared", "isolated"])
def test_csharp_request_reaches_algorithm_unchanged(kind: str) -> None:
    capture = Path(os.environ["RAW_DATA_CAPTURE_PATH"])
    request = json.loads(capture.read_text(encoding="utf-8-sig"))
    registry = AlgorithmRegistry()
    registry.register(AlgorithmSpec(
        name="raw_interop", version="v1", description="C# interoperability",
        created_time="2026-11-13", author="qa", category="unit",
        application_scenarios="test", input_model=PredictionRequest,
        output_model=InteropResult, algorithm_type=AlgorithmType.PREDICTION,
        execution=ExecutionConfig(
            execution_mode=(ExecutionMode.IN_PROCESS if kind == "in_process"
                            else ExecutionMode.PROCESS_POOL),
            isolated_pool=kind == "isolated", max_workers=1,
        ), entrypoint=InteropAlgorithm, is_class=True,
    ))
    expected = sha256(json.dumps(
        request["rawData"], sort_keys=True,
    ).encode()).hexdigest()
    with TestClient(create_app(registry)) as client:
        response = client.post("/algorithms/raw_interop/v1", json=request)
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0, body
        assert body["data"] == {
            "digest": expected, "satelliteId": 123, "customPower": 250,
        }
        assert "rawData" not in body
