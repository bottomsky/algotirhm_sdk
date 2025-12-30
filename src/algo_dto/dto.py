from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from algo_dto.base import Vector6, SimTime


class CamelBaseModel(BaseModel):
    """Base model that automatically converts snake_case fields to camelCase JSON."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class SatOrbitJ2000(CamelBaseModel):
    j2000_rv: Vector6
    sat_id: int


class SatOrbitVVLHRv(CamelBaseModel):
    vvlh_rv: Vector6
    sat_id: int


class PredictionRequest(CamelBaseModel):
    sat_states: SatOrbitVVLHRv
    target_sats: list[SatOrbitVVLHRv]
    sim_time: SimTime
    duration_s: float = Field(alias="duration_s")


class PredictionResponseItem(CamelBaseModel):
    min_distance: float
    relative_state_vvlh: list[Vector6]
    sore: float
    t_nearest_time: SimTime
