"""Contract tests against actual LJ.DTO Web-serialized JSON and metadata."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import pickle
import subprocess
import sys
from typing import Any

import pytest
from pydantic import ValidationError

from algo_dto import csharp_models
from algo_dto.condition import ConditionRequest
from algo_dto.csharp_models import (
    EquipmentParam,
    ForceEquipment,
    LaserPayloadParam,
    PlatEvent,
    PlatParam,
    ProjectDTO,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads(
    (ROOT / "tests/fixtures/csharp_condition_contract.json").read_text(
        encoding="utf-8-sig"
    )
)


@pytest.mark.parametrize("name", CONTRACT["models"])
def test_all_csharp_serialized_properties_are_typed(name: str) -> None:
    model = getattr(csharp_models, name)
    expected = CONTRACT["models"][name]["properties"]
    actual = {field.alias: field for field in model.model_fields.values()}
    assert actual.keys() == {prop["alias"] for prop in expected}
    assert "Any" not in str(model.__annotations__)
    for prop in expected:
        field = actual[prop["alias"]]
        assert field.json_schema_extra == (
            {"readOnly": True} if prop["readOnly"] else None
        )


def test_full_csharp_payload_has_nested_models_and_scalar_types() -> None:
    req = ConditionRequest.model_validate(CONTRACT["conditionData"])
    assert isinstance(req.project_dto, ProjectDTO)
    equipment = req.project_dto.force.equipment[0]
    assert isinstance(equipment, ForceEquipment)
    assert isinstance(equipment.equipment_param, EquipmentParam)
    assert isinstance(equipment.equipment_param.plat_param, PlatParam)
    laser = equipment.equipment_param.payload_params[0].laser_payload_param
    assert isinstance(laser, LaserPayloadParam)
    assert laser.strike_distance == 1.5  # Inherited C# property.
    assert isinstance(laser.can_battle_time, datetime)
    state = req.frame_data.data["1001"]
    assert state.vvlh_rv.root == [1, 2, 3, 4, 5, 6]
    assert state.sat_rv is not None
    assert state.sat_rv.root == [1, 2, 3, 4, 5, 6]
    assert isinstance(req.frame_data.platform_event[0], PlatEvent)
    assert req.frame_data.platform_event[0].event_content == b"\x01\x02\xff"
    assert pickle.loads(pickle.dumps(req)) == req


def assert_json_equivalent(actual: Any, expected: Any) -> None:
    """Compare values while allowing equivalent ISO datetime formatting."""
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_json_equivalent(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for item, wanted in zip(actual, expected):
            assert_json_equivalent(item, wanted)
    elif isinstance(expected, str) and isinstance(actual, str):
        if actual != expected:
            assert datetime.fromisoformat(actual) == datetime.fromisoformat(
                expected
            )
    else:
        assert actual == expected


def test_complete_csharp_json_round_trips_without_losing_properties() -> None:
    req = ConditionRequest.model_validate(CONTRACT["conditionData"])
    actual = req.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert_json_equivalent(actual, CONTRACT["conditionData"])


def test_unknown_fields_survive_at_every_nested_level() -> None:
    data = deepcopy(CONTRACT["conditionData"])
    extra = {"huge": 123456789012345678901234567890, "values": [None, "002"]}
    project = data["projectDto"]
    project["custom"] = extra
    equipment = project["force"]["equipment"][0]
    equipment["equipmentParam"]["platParam"]["custom"] = extra
    equipment["equipmentParam"]["payloadParams"][0]["newPayload"] = extra
    data["frameData"]["data"]["1001"]["custom"] = extra
    req = ConditionRequest.model_validate(data)
    assert req.project_dto.model_extra == {"custom": extra}
    actual = req.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert_json_equivalent(actual, data)


def test_exact_nonstandard_csharp_aliases_and_independent_defaults() -> None:
    project = ProjectDTO.model_validate({
        "force": {"equipment": [{
            "uuid": "9007199254740993", "relations ": 3,
            "equipmentParam": {"platParam": {
                "algorithmsSatType": 22, "Isp": 5, "Thrust": 8,
                "I": [[1, 0], [0, 1]], "m_TarSize": [1, 2, 3],
                "attitude": {"AttReFrame": "J2000", "RotationOrderNum": 321},
            }},
        }]},
    })
    equipment = project.force.equipment[0]
    assert equipment.uuid == 9007199254740993
    assert equipment.relations == 3
    platform = equipment.equipment_param.plat_param
    assert platform.sat_type == 22
    assert platform.attitude.att_ref_frame == "J2000"
    dumped = project.model_dump(mode="json", by_alias=True)
    platform_json = dumped["force"]["equipment"][0]["equipmentParam"]
    assert platform_json["platParam"]["algorithmsSatType"] == 22
    assert "RawData" not in ProjectDTO.model_fields
    first, second = ProjectDTO(), ProjectDTO()
    first.force.equipment.append(equipment)
    assert second.force.equipment == []


@pytest.mark.parametrize("bad", ["invalid", [1, 2], {"x": 1}])
def test_known_vector_types_are_validated(bad: Any) -> None:
    with pytest.raises(ValidationError):
        PlatParam.model_validate({"dwellDis": bad})


def test_codegen_is_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "models.py"
    subprocess.run([
        sys.executable, str(ROOT / "scripts/generate_csharp_models.py"),
        "--output", str(output),
    ], check=True, capture_output=True)
    assert output.read_bytes() == (
        ROOT / "src/algo_dto/csharp_models.py"
    ).read_bytes()
