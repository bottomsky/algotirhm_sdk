from __future__ import annotations

from algo_dto.base import CamelBaseModel, Vector3


class ControlledMap(CamelBaseModel):
    diss_coe: int
    area: int
    relative_v: Vector3
    relative_w: Vector3
    evasion_ang: Vector3
    operation_interval: int
    operation_num: int
    operation_dis: int


class DnMap(CamelBaseModel):
    relative_v: Vector3
    evasion_ang: Vector3
    bom_num: int
    release_dis: int


class LaserMap(CamelBaseModel):
    relative_w: Vector3
    evasion_ang: Vector3
    area: float
    diss_code: float
    laser_time: int
    battle_interval: int


class PlatformMap(CamelBaseModel):
    single_maneuver: int
    all_manuever: int
    orbit_ctrl_interval: int
