import json

import pytest
from pydantic import BaseModel, ValidationError

from algo_dto.base import Vector2, Vector3, Vector4, Vector6
from algo_dto.dto import OrbitAng


class Payload(BaseModel):
    vec: Vector3


def test_vector_accepts_sequence_and_serializes_as_array() -> None:
    vec = Vector2.model_validate([1, 2])
    assert vec.to_list() == [1.0, 2.0]
    assert list(vec) == [1.0, 2.0]

    payload = json.loads(vec.model_dump_json())
    assert payload == [1.0, 2.0]

    model = Payload(vec=Vector3.model_validate((1, 2, 3)))
    assert model.model_dump() == {"vec": [1.0, 2.0, 3.0]}


def test_vector_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        Vector3.model_validate([1, 2])

    with pytest.raises(ValidationError):
        Vector6.model_validate([1, 2, 3, 4, 5])


def test_vector_from_values_helper() -> None:
    vec = Vector4.from_values(1, 2, 3, 4)
    assert vec.to_tuple() == (1.0, 2.0, 3.0, 4.0)


def test_timestamp_accepts_sim_time_and_start_time_aliases() -> None:
    payload_sim_time = {
        "id": "ang-1",
        "simTime": [2025, 1, 1, 0, 0, 0],
        "aimAxis": [0.0, 0.0, 1.0],
    }
    model_sim_time = OrbitAng.model_validate(payload_sim_time)
    assert model_sim_time.sim_time.root == [2025, 1, 1, 0, 0, 0]

    payload_start_time = {
        "id": "ang-1",
        "startTime": [2025, 1, 1, 0, 0, 0],
        "aimAxis": [0.0, 0.0, 1.0],
    }
    model_start_time = OrbitAng.model_validate(payload_start_time)
    assert model_start_time.sim_time.root == [2025, 1, 1, 0, 0, 0]
