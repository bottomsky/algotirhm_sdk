from __future__ import annotations

from pydantic import Field

from algo_dto.base import (
    CamelBaseModel,
    TimeRange,
    Timestamp,
    Vector4,
    Vector6,
    SimTime,
    Vector3,
)


class SatBase(CamelBaseModel):
    sat_id: int


class SatTypeBase(SatBase, CamelBaseModel):
    sat_type: int


class SatOrbitJ2000(SatBase, CamelBaseModel):
    j2000_rv: Vector6


class SatOrbitVVLHRv(SatBase, CamelBaseModel):
    vvlh_rv: Vector6


class SatOrbit(SatOrbitVVLHRv, SatOrbitJ2000):
    pass


class PredictionRequest(CamelBaseModel):
    sat_states: SatOrbitVVLHRv
    target_sats: list[SatOrbitVVLHRv]
    sim_time: SimTime
    duration_s: float = Field(alias="duration_s")


class ControlledMap(CamelBaseModel):
    diss_coe: int
    area: int
    relative_v: Vector3
    relative_w: Vector3
    evasion_ang: Vector3
    peration_interval: int
    operation_num: int
    operation_dis: int


class PlatformMap(CamelBaseModel):
    single_maneuver: int
    all_manuever: int
    orbit_ctrl_interval: int


class PredictionResponseItem(CamelBaseModel):
    min_distance: float
    relative_state_vvlh: list[Vector6]
    sore: float
    t_nearest_time: SimTime


class PlanningTarget(SatOrbit, CamelBaseModel):
    dwellDis: Vector3
    dwellTime: Vector3
    spray_time: int
    power_density: Vector3
    miss_dis: int
    fixed_axis: Vector3
    q4: Vector4
    sat_type: int
    palnning_id: str


class PlanningSource(SatOrbit, CamelBaseModel):
    controlled_map: ControlledMap
    platform_map: PlatformMap
    fixed_axis: Vector3
    q4: Vector4
    sat_type: int


class PlanningBase(CamelBaseModel):
    planning_id: str
    task_id: str
    sub_task_id: str


class Planning(PlanningBase, CamelBaseModel):
    target: PlanningTarget
    source: PlanningSource
    task_time_start: SimTime
    task_time_end: SimTime
    task_mode: int
    planning_id: str
    algorithm_name: str


class ControlledBase(CamelBaseModel):
    id: str


class ControlledData(ControlledBase, TimeRange, CamelBaseModel):
    pass


class OrbitManInfo(ControlledBase, Timestamp, CamelBaseModel):
    devlta_v: Vector3
    sim_time: SimTime
    system: int


class OrbitAng(ControlledBase, Timestamp, CamelBaseModel):
    aim_aixs: Vector3


class ProgrammeResult(SatTypeBase, PlanningBase, CamelBaseModel):
    controlled_data: list[ControlledData]
    orbit_ang: list[OrbitAng]
    task_mode: int


class ProgrammeRequest(CamelBaseModel):
    sat: SatOrbitJ2000
    plannings: list[Planning]
    sim_time: SimTime
