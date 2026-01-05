from __future__ import annotations

from pydantic import Field, RootModel

from algo_dto.base import (
    VVLHRV,
    CamelBaseModel,
    SimTime,
    TimeRange,
    Timestamp,
    Vector3,
    Vector4,
    Vector6,
)
from algo_dto.device import ControlledMap, DnMap, LaserMap, PlatformMap


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


class SatTypeOrbit(SatOrbitVVLHRv, SatOrbitJ2000):
    sat_type: int


class PredictionRequest(CamelBaseModel):
    sat_states: SatOrbitVVLHRv
    target_sats: list[SatOrbitVVLHRv]
    sim_time: SimTime
    duration_s: float = Field(alias="duration_s")


class TargetSatBase(SatOrbit, CamelBaseModel):
    dwellDis: Vector3
    dwellTime: Vector3
    spray_time: int
    power_density: Vector3
    miss_dis: int
    fixed_axis: Vector3
    q4: Vector4
    sat_type: int


class PlanningSource(SatOrbit, CamelBaseModel):
    controlled_map: ControlledMap
    platform_map: PlatformMap
    fixed_axis: Vector3
    q4: Vector4
    sat_type: int


class TaskBase(CamelBaseModel):
    task_id: str
    sub_task_id: str


class PlanningBase(TaskBase, CamelBaseModel):
    planning_id: str


class Planning(PlanningBase, CamelBaseModel):
    target: TargetSatBase
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


class LaserData(ControlledBase, Timestamp, CamelBaseModel):
    pass


class OrbitManInfo(ControlledBase, Timestamp, CamelBaseModel):
    delta_v: Vector3
    sim_time: SimTime
    system: int


class OrbitAng(ControlledBase, Timestamp, CamelBaseModel):
    aim_axis: Vector3


class ProgrammeResponse(CamelBaseModel):
    result: ProgrammeResult


class PrepareSource(SatTypeOrbit, CamelBaseModel):
    controlled_map: ControlledMap
    fixed_axis: Vector3
    q4: Vector4
    controlled_map: ControlledMap
    platform_map: PlatformMap
    laser_map: LaserMap
    dn_map: DnMap


class Prepare(TaskBase, TimeRange, CamelBaseModel):
    target_sats: list[TargetSatBase]
    source: list[PlanningSource]
    algorithm_name: str


class PrepareRequest(CamelBaseModel):
    """
    规划算法的请求信息
    """

    sat: SatOrbitJ2000
    sim_time: SimTime
    task: list[Prepare]


class PrepareResultItem(SatBase, TimeRange, TaskBase, CamelBaseModel):
    """
    规划算法的结果信息
    """

    task_mode: int


class PrepareResult(RootModel[dict[str, PrepareResultItem]], CamelBaseModel):
    """规划算法的结果信息（字典形式）

    Key: str
    Value: PrepareResultItem
    """

    model_config = CamelBaseModel.model_config


class PredictionResultItem(SatBase, CamelBaseModel):
    """
    预测算法的结果信息项
    """

    min_distance: float
    relative_state_vvlh: VVLHRV
    score: float
    t_nearest_time: SimTime


class PredictionResult(RootModel[list[PredictionResultItem]], CamelBaseModel):
    """
    预测算法的结果信息
    """

    model_config = CamelBaseModel.model_config


class ProgrammeResultItem(SatTypeBase, PlanningBase, CamelBaseModel):
    """
    规划算法的结果信息项
    """

    controlled_data: list[ControlledData]
    orbit_ang: list[OrbitAng]
    task_mode: int
    orbit_man_info: list[OrbitManInfo]
    laser_data: list[LaserData]


class ProgrammeResult(RootModel[list[ProgrammeResultItem]], CamelBaseModel):
    """
    规划算法的结果信息
    """

    model_config = CamelBaseModel.model_config


class ProgrammeRequest(CamelBaseModel):
    sat: SatOrbitJ2000
    plannings: list[Planning]
    sim_time: SimTime
