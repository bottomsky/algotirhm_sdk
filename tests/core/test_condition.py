from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from algo_core_service.algorithms.condition import ConditionAlgorithm
from algo_dto.condition import ConditionRequest


@pytest.mark.parametrize(
    ("satellites", "expected"),
    [
        ({"1001": {"forceType": 1, "isSatFault": 1}}, True),
        ({"1001": {"forceType": 2, "isSatFault": 1}}, False),
        ({"1001": {"forceType": 1, "isSatFault": 0}}, False),
        ({"1001": {"forceType": 1, "isSatFault": 2}}, False),
        ({}, False),
        (
            {
                "1001": {"forceType": 2, "isSatFault": 1},
                "1002": {"forceType": 1, "isSatFault": 0},
            },
            False,
        ),
        (
            {
                "1001": {"forceType": 2, "isSatFault": 1},
                "1002": {"forceType": 1, "isSatFault": 1},
            },
            True,
        ),
    ],
)
def test_condition_result(
    satellites: dict[str, dict[str, int]], expected: bool
) -> None:
    req = ConditionRequest.model_validate(
        {
            "frameData": {"data": satellites},
            "projectDto": {},
            "forceType": 1,
        }
    )
    result = ConditionAlgorithm().run(req)
    assert result.root is expected
    assert result.model_dump(mode="json") is expected


@pytest.mark.parametrize("field_name", ["satId", "sateId", "sat_id"])
def test_satellite_id_aliases(field_name: str) -> None:
    req = ConditionRequest.model_validate(
        {
            "frameData": {"data": {}},
            "projectDto": {},
            "forceType": 1,
            field_name: "1001",
        }
    )
    assert req.sat_id == "1001"
    assert req.model_dump(by_alias=True)["satId"] == "1001"
    assert "sateId" not in req.model_dump(by_alias=True)


def test_satellite_id_defaults_to_empty() -> None:
    req = ConditionRequest.model_validate(
        {"frameData": {"data": {}}, "projectDto": {}, "forceType": 1}
    )
    assert req.sat_id == ""


def test_accepts_extra_simulation_fields() -> None:
    req = ConditionRequest.model_validate(
        {
            "frameData": {
                "time": 10,
                "data": {
                    "1001": {
                        "forceType": 1,
                        "isSatFault": 1,
                        "id": 1001,
                        "vvlhrv": {"position": [1, 2, 3]},
                    }
                },
            },
            "projectDto": {"id": "demo", "settings": {"enabled": True}},
            "forceType": 1,
            "extraContext": "ignored",
        }
    )
    assert req.project_dto.id == "demo"
    assert req.project_dto.model_extra == {"settings": {"enabled": True}}
    assert req.model_dump(by_alias=True)["forceType"] == 1
    assert ConditionAlgorithm().run(req).root is True


@pytest.mark.parametrize(
    "payload",
    [
        {"projectDto": {}, "forceType": 1},
        {"frameData": {}, "projectDto": {}, "forceType": 1},
        {"frameData": {"data": {}}, "forceType": 1},
        {"frameData": {"data": {}}, "projectDto": {}},
        {"frameData": {"data": []}, "projectDto": {}, "forceType": 1},
        {"frameData": {"data": {}}, "projectDto": [], "forceType": 1},
        {
            "frameData": {"data": {}},
            "projectDto": {},
            "forceType": "invalid",
        },
        *[
            {
                "frameData": {"data": {"1001": state}},
                "projectDto": {},
                "forceType": 1,
            }
            for state in [
                {"forceType": 1},
                {"isSatFault": 1},
                {"forceType": "invalid", "isSatFault": 1},
                {"forceType": 1, "isSatFault": "invalid"},
                {"forceType": 1, "isSatFault": None},
            ]
        ],
    ],
)
def test_invalid_condition_request(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConditionRequest.model_validate(payload)
