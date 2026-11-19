"""Generated C# ProjectDTO/SimData wire models (LJ.DTO 1.0.12).

Regenerate using scripts/generate_csharp_models.py.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Base64Bytes, ConfigDict, Field, JsonValue

from algo_dto.base import CamelBaseModel, Vector3, Vector4, Vector6


class CSharpDtoModel(CamelBaseModel):
    """Typed properties with forward-compatible JSON extras."""

    model_config = ConfigDict(extra="allow")


class SpaceWeatherContainer(CSharpDtoModel):
    """Serialized LJ.DTO.SpaceWeatherContainer properties."""

    space_weather: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='spaceWeather',
    )


class ScenarioWeather(CSharpDtoModel):
    """Serialized LJ.DTO.ScenarioWeather properties."""

    space_weather: SpaceWeatherContainer = Field(
        default_factory=lambda: SpaceWeatherContainer(),
        alias='spaceWeather',
    )


class EnvironmentConfig(CSharpDtoModel):
    """Serialized LJ.DTO.EnvironmentConfig properties."""

    scenario_weather: ScenarioWeather = Field(
        default_factory=lambda: ScenarioWeather(),
        alias='scenarioWeather',
    )


class EquipmentState(CSharpDtoModel):
    """Serialized LJ.DTO.EquipmentState properties."""

    angle: JsonValue | None = Field(
        default=None,
        alias='angle',
    )
    is_injure: JsonValue | None = Field(
        default=None,
        alias='isInjure',
    )
    mpoint: JsonValue | None = Field(
        default=None,
        alias='mpoint',
    )
    speed: JsonValue | None = Field(
        default=None,
        alias='speed',
    )
    type: JsonValue | None = Field(
        default=None,
        alias='type',
    )
    work_status: JsonValue | None = Field(
        default=None,
        alias='workStatus',
    )


class PayloadCcsPayParam(CSharpDtoModel):
    """Serialized LJ.DTO.PayloadCcsPayParam properties."""

    angle: JsonValue | None = Field(
        default=None,
        alias='angle',
    )
    azimuth: JsonValue | None = Field(
        default=None,
        alias='azimuth',
    )
    azimuth_range: JsonValue | None = Field(
        default=None,
        alias='azimuthRange',
    )
    elevation: JsonValue | None = Field(
        default=None,
        alias='elevation',
    )
    elevation_range: JsonValue | None = Field(
        default=None,
        alias='elevationRange',
    )
    explore_power: JsonValue | None = Field(
        default=None,
        alias='explorePower',
    )
    is_injure: JsonValue | None = Field(
        default=None,
        alias='isInjure',
    )
    scan: JsonValue | None = Field(
        default=None,
        alias='scan',
    )
    scan_distance: JsonValue | None = Field(
        default=None,
        alias='scanDistance',
    )
    sm_list: JsonValue | None = Field(
        default=None,
        alias='smList',
    )
    work_status: JsonValue | None = Field(
        default=None,
        alias='workStatus',
    )


class EquipmentUnit(CSharpDtoModel):
    """Serialized LJ.DTO.EquipmentUnit properties."""

    equip_gb: str = Field(
        default='',
        alias='equipGb',
    )
    equip_no: str = Field(
        default='',
        alias='equipNo',
    )
    equipment: list[EquipmentUnit] = Field(
        default_factory=list,
        alias='equipment',
    )
    equipment_param: EquipmentState = Field(
        default_factory=lambda: EquipmentState(),
        alias='equipmentParam',
    )
    optical_perception_param: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='opticalPerceptionParam',
    )
    payload_adsorption_param: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='payloadAdsorptionParam',
    )
    payload_base_info_param: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='payloadBaseInfoParam',
    )
    payload_ccs_pay_param: PayloadCcsPayParam = Field(
        default_factory=lambda: PayloadCcsPayParam(),
        alias='payloadCCSPayParam',
    )
    payload_ck_camera_pay_param: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='payloadCKCameraPayParam',
    )
    payload_ck_jxb_param: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias='payloadCKJXBParam',
    )


class OrbitElements(CSharpDtoModel):
    """Serialized LJ.DTO.OrbitElements properties."""

    eccentricity: float = Field(
        default=0,
        alias='ecc',
    )
    inclination: float = Field(
        default=0,
        alias='i',
    )
    right_ascension: float = Field(
        default=0,
        alias='raan',
    )
    argument_of_perigee: float = Field(
        default=0,
        alias='argPeri',
    )
    mean_anomaly: float = Field(
        default=0,
        alias='meanA',
    )
    semi_major_axis: float = Field(
        default=0,
        alias='sMajAx',
    )


class ForceModel(CSharpDtoModel):
    """Serialized LJ.DTO.ForceModel properties."""

    gravity_degree: int = Field(
        default=0,
        alias='gravityDegree',
    )
    gravity_order: int = Field(
        default=0,
        alias='gravityOrder',
    )
    drag_coeff: float = Field(
        default=0,
        alias='dragCoeff',
    )
    ca: float = Field(
        default=0,
        alias='ca',
    )
    cs: float = Field(
        default=0,
        alias='cs',
    )
    cr: float = Field(
        default=0,
        alias='cr',
    )
    daily_flux: float = Field(
        default=0,
        alias='dailyFlux',
    )
    average_flux: float = Field(
        default=0,
        alias='averageFlux',
    )
    ap: float = Field(
        default=0,
        alias='ap',
    )


class MassArea(CSharpDtoModel):
    """Serialized LJ.DTO.MassArea properties."""

    mass: float = Field(
        default=0,
        alias='mass',
    )
    drag_section: float = Field(
        default=0,
        alias='dragSection',
    )
    solar_cross: float = Field(
        default=0,
        alias='solarCross',
    )


class Attitude(CSharpDtoModel):
    """Serialized LJ.DTO.Attitude properties."""

    att_ref_frame: str = Field(
        default='',
        alias='AttReFrame',
    )
    rotation_order_num: int = Field(
        default=0,
        alias='RotationOrderNum',
    )
    euler_1: float = Field(
        default=0,
        alias='Euler1',
    )
    euler_2: float = Field(
        default=0,
        alias='Euler2',
    )
    euler_3: float = Field(
        default=0,
        alias='Euler3',
    )


class Capability(CSharpDtoModel):
    """Serialized LJ.DTO.Capability properties."""

    score: float = Field(
        default=0,
        alias='score',
    )


class ManeuverCapability(CSharpDtoModel):
    """Serialized LJ.DTO.ManeuverCapability properties."""

    score: float = Field(
        default=0,
        alias='score',
    )
    isp: float = Field(
        default=0,
        alias='isp',
    )
    thrust: float = Field(
        default=0,
        alias='thrust',
    )
    single_max_delta_v: float = Field(
        default=0,
        alias='singleMaxDeltaV',
    )
    total_delta_v: float = Field(
        default=0,
        alias='totalDeltaV',
    )
    orbit_ctrl_interval: float = Field(
        default=0,
        alias='orbitCtrlInterval',
    )


class InformationCapability(CSharpDtoModel):
    """Serialized LJ.DTO.InformationCapability properties."""

    score: float = Field(
        default=0,
        alias='score',
    )
    target_guidance: str = Field(
        default='',
        alias='targetGuidance',
    )
    tm_bandwidth: float = Field(
        default=0,
        alias='tmBandwidth',
    )


class PerceptionCapability(CSharpDtoModel):
    """Serialized LJ.DTO.PerceptionCapability properties."""

    score: float = Field(
        default=0,
        alias='score',
    )
    target_num: int = Field(
        default=0,
        alias='targetNum',
    )
    detection_distance: float = Field(
        default=0,
        alias='detectionDistance',
    )


class PlatParam(CSharpDtoModel):
    """Serialized LJ.DTO.PlatParam properties."""

    sat_type: int = Field(
        default=0,
        alias='algorithmsSatType',
    )
    dyn_type: int = Field(
        default=0,
        alias='dynType',
    )
    dwell_dis: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='dwellDis',
    )
    spray_time: float = Field(
        default=0,
        alias='sprayTime',
    )
    sat_mass: float = Field(
        default=0,
        alias='satMass',
    )
    fuel_mass: float = Field(
        default=0,
        alias='fuelMass',
    )
    miss_dis: float = Field(
        default=0,
        alias='missDis',
    )
    orbit_epoch: str = Field(
        default='',
        alias='orbitEpoch',
    )
    orbit_init_type: int = Field(
        default=0,
        alias='orbitInitType',
    )
    orbit_type: int = Field(
        default=0,
        alias='orbitType',
    )
    power_density: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='powerDensity',
    )
    sat_rv: list[float] | None = Field(
        default=None,
        alias='satRV',
    )
    orbit_tle: str | None = Field(
        default=None,
        alias='orbitTLE',
    )
    orbit_elements: OrbitElements = Field(
        default_factory=lambda: OrbitElements(),
        alias='orbitElem',
    )
    euler_ang: list[float] | None = Field(
        default=None,
        alias='eulerAng',
    )
    omega: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='omega',
    )
    orbit_ctrl_err: float = Field(
        default=0,
        alias='orbitCtrlErr',
    )
    orbit_ctrl_interval: float = Field(
        default=0,
        alias='orbitCtrlInterval',
    )
    target_size: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='m_TarSize',
    )
    euler_seq: int = Field(
        default=0,
        alias='eulerSeq',
    )
    force_model: ForceModel = Field(
        default_factory=lambda: ForceModel(),
        alias='forceModel',
    )
    mass_area: MassArea = Field(
        default_factory=lambda: MassArea(),
        alias='massArea',
    )
    attitude: Attitude = Field(
        default_factory=lambda: Attitude(),
        alias='attitude',
    )
    strike_capability: Capability = Field(
        default_factory=lambda: Capability(),
        alias='strikeCapability',
    )
    protect_capability: Capability = Field(
        default_factory=lambda: Capability(),
        alias='protectCapability',
    )
    maneuver_capability: ManeuverCapability = Field(
        default_factory=lambda: ManeuverCapability(),
        alias='maneuverCapability',
    )
    information_capability: InformationCapability = Field(
        default_factory=lambda: InformationCapability(),
        alias='informationCapability',
    )
    perception_capability: PerceptionCapability = Field(
        default_factory=lambda: PerceptionCapability(),
        alias='perceptionCapability',
    )
    isp: float = Field(
        default=0,
        alias='Isp',
    )
    thrust: float = Field(
        default=0,
        alias='Thrust',
    )
    inertia_matrix: list[list[float]] = Field(
        default_factory=list,
        alias='I',
    )
    dwell_time: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='dwellTime',
    )
    can_battle_time: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '0001-01-01T00:00:00'
        ),
        alias='canBattleTime',
    )


class LaserPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.LaserPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    strike_distance: float = Field(
        default=0,
        alias='strikeDistance',
    )
    relative_w: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='relativeW',
    )
    area: float = Field(
        default=0,
        alias='area',
    )
    diss_coe: float = Field(
        default=0,
        alias='dissCoe',
    )
    evasion_ang: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='evasionAng',
    )
    power: float = Field(
        default=0,
        alias='power',
    )
    laser_time: float = Field(
        default=0,
        alias='laserTime',
    )
    battle_interval: float = Field(
        default=0,
        alias='battleInterval',
    )
    can_battle_time: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '0001-01-01T00:00:00'
        ),
        alias='canBattleTime',
    )


class DnPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.DnPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    relative_v: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='relativeV',
    )
    evasion_ang: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='evasionAng',
    )
    bomb_num: int = Field(
        default=0,
        alias='bombNum',
    )
    release_dis: float = Field(
        default=0,
        alias='releaseDis',
    )
    can_battle_time: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '0001-01-01T00:00:00'
        ),
        alias='canBattleTime',
    )
    strike_distance: float = Field(
        default=0,
        alias='strikeDistance',
    )


class ControlledPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.ControlledPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    relative_w: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='relativeW',
    )
    relative_v: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='relativeV',
    )
    evasion_ang: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='evasionAng',
    )
    operation_dis: float = Field(
        default=0,
        alias='operationDis',
    )
    operation_interval: float = Field(
        default=0,
        alias='operationInterval',
    )
    operation_num: int = Field(
        default=0,
        alias='operationNum',
    )
    can_battle_time: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '0001-01-01T00:00:00'
        ),
        alias='canBattleTime',
    )


class InterferencePayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.InterferencePayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    payload_direction: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='payloadDirection',
    )
    angle_range: float = Field(
        default=0,
        alias='angleRange',
    )


class RadarPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.RadarPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    payload_direction: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='payloadDirection',
    )
    angle_range: float = Field(
        default=0,
        alias='angleRange',
    )


class CommunicationPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.CommunicationPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    communication_distance: float = Field(
        default=0,
        alias='communicationDistance',
    )


class InfraredPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.InfraredPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    payload_direction: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='payloadDirection',
    )
    angle_range: float = Field(
        default=0,
        alias='angleRange',
    )


class OpticsPayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.OpticsPayloadParam properties."""

    install_matrix: str = Field(
        default='1',
        alias='installMatrix',
    )
    payload_direction: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='payloadDirection',
    )
    angle_x_range: float = Field(
        default=0,
        alias='angleXRange',
    )
    angle_y_range: float = Field(
        default=0,
        alias='angleYRange',
    )


class PayloadParam(CSharpDtoModel):
    """Serialized LJ.DTO.PayloadParam properties."""

    laser_payload_param: LaserPayloadParam | None = Field(
        default=None,
        alias='laserPayloadParam',
    )
    dn_payload_param: DnPayloadParam | None = Field(
        default=None,
        alias='dnPayloadParam',
    )
    controlled_payload_param: ControlledPayloadParam | None = Field(
        default=None,
        alias='controlledPayloadParam',
    )
    interference_payload_param: InterferencePayloadParam | None = Field(
        default=None,
        alias='interferencePayloadParam',
    )
    radar_payload_param: RadarPayloadParam | None = Field(
        default=None,
        alias='radarPayloadParam',
    )
    communication_payload_param: CommunicationPayloadParam | None = Field(
        default=None,
        alias='communicationPayloadParam',
    )
    infrared_payload_param: InfraredPayloadParam | None = Field(
        default=None,
        alias='infraredPayloadParam',
    )
    optics_payload_param: OpticsPayloadParam | None = Field(
        default=None,
        alias='opticsPayloadParam',
    )


class EquipmentParam(CSharpDtoModel):
    """Serialized LJ.DTO.EquipmentParam properties."""

    plat_param: PlatParam = Field(
        default_factory=lambda: PlatParam(),
        alias='platParam',
    )
    payload_params: list[PayloadParam] = Field(
        default_factory=list,
        alias='payloadParams',
    )


class ForceEquipment(CSharpDtoModel):
    """Serialized LJ.DTO.ForceEquipment properties."""

    equip_gb: str = Field(
        default='',
        alias='equipGb',
    )
    equip_no: str = Field(
        default='',
        alias='equipNo',
    )
    equipment: list[EquipmentUnit] | None = Field(
        default=None,
        alias='equipment',
    )
    equipment_param: EquipmentParam = Field(
        default_factory=lambda: EquipmentParam(),
        alias='equipmentParam',
    )
    force_side: int = Field(
        default=0,
        alias='forceSide',
    )
    is_active: bool = Field(
        default=False,
        alias='isActive',
    )
    model_name: str = Field(
        default='',
        alias='modelName',
    )
    name: str = Field(
        default='',
        alias='name',
    )
    relations: int = Field(
        default=0,
        alias='relations ',
    )
    skill: str = Field(
        default='',
        alias='skill',
    )
    status: int = Field(
        default=0,
        alias='status',
    )
    three_d_url: str = Field(
        default='',
        alias='threeDUrl',
    )
    uuid: int = Field(
        default=0,
        alias='uuid',
    )
    vip: bool = Field(
        default=False,
        alias='vip',
    )
    standard: bool = Field(
        default=False,
        alias='standard',
    )


class ForceConfig(CSharpDtoModel):
    """Serialized LJ.DTO.ForceConfig properties."""

    equipment: list[ForceEquipment] = Field(
        default_factory=list,
        alias='equipment',
    )


class Scenario(CSharpDtoModel):
    """Serialized LJ.DTO.Scenario properties."""

    description: str = Field(
        default='',
        alias='description',
    )
    keywords: list[str] = Field(
        default_factory=list,
        alias='keywords',
    )
    modification_date: str = Field(
        default='',
        alias='modificationDate',
    )
    name: str = Field(
        default='',
        alias='name',
    )
    scene_id: int = Field(
        default=0,
        alias='sceneId',
    )
    version: str = Field(
        default='',
        alias='version',
    )


class ProjectDTO(CSharpDtoModel):
    """Serialized LJ.DTO.ProjectDTO properties."""

    distributed: bool = Field(
        default=False,
        alias='distributed',
    )
    environment: EnvironmentConfig = Field(
        default_factory=lambda: EnvironmentConfig(),
        alias='environment',
    )
    equipment_num_each_node: int = Field(
        default=0,
        alias='equipmentNumEachNode',
    )
    force: ForceConfig = Field(
        default_factory=lambda: ForceConfig(),
        alias='force',
    )
    id: str = Field(
        default='',
        alias='id',
    )
    scenario: Scenario = Field(
        default_factory=lambda: Scenario(),
        alias='scenario',
    )


class ScriptVo(CSharpDtoModel):
    """Serialized LJ.DTO.Engine.ScriptVo properties."""

    equipment_id: int = Field(
        default=0,
        alias='equipmentId',
    )
    type: int = Field(
        default=0,
        alias='type',
    )
    data: JsonValue = Field(
        default=None,
        alias='data',
    )


class SimSatSimulation(CSharpDtoModel):
    """Serialized LJ.DTO.Engine.SimSatSimulation properties."""

    id: int = Field(
        default=0,
        alias='id',
    )
    vvlh_rv: Vector6 = Field(
        default_factory=lambda: Vector6([0, 0, 0, 0, 0, 0]),
        alias='vvlhRv',
    )
    ecf: Vector6 | None = Field(
        default=None,
        alias='ecf',
    )
    m_name: str = Field(
        default='',
        alias='m_Name',
    )
    force_type: int = Field(
        default=0,
        alias='forceType',
    )
    model_type: int = Field(
        default=0,
        alias='modelType',
    )
    fuel_mass: float | None = Field(
        default=None,
        alias='fuelMass',
    )
    sat_rv: Vector6 | None = Field(
        default=None,
        alias='satRV',
    )
    sat_coe: Vector6 | None = Field(
        default=None,
        alias='satCoe',
    )
    is_pulse: bool | None = Field(
        default=None,
        alias='isPulse',
    )
    sat_close_control_model: int | None = Field(
        default=None,
        alias='satCloseControlModel',
    )
    euler: Vector3 | None = Field(
        default=None,
        alias='euler',
    )
    q: Vector4 | None = Field(
        default=None,
        alias='q',
    )
    omega: Vector3 | None = Field(
        default=None,
        alias='omega',
    )
    mode: int | None = Field(
        default=None,
        alias='mode',
    )
    is_steady_atti: bool | None = Field(
        default=None,
        alias='isSteadyAtti',
    )
    navi_target: int | None = Field(
        default=None,
        alias='naviTarget',
    )
    is_keep_navi: bool | None = Field(
        default=None,
        alias='isKeepNavi',
    )
    is_sat_fault: int = Field(
        default=0,
        alias='isSatFault',
    )
    lat: float | None = Field(
        default=None,
        alias='lat',
    )
    lon: float | None = Field(
        default=None,
        alias='lon',
    )
    alt: float | None = Field(
        default=None,
        alias='alt',
    )
    payloads: PayloadParam = Field(
        default_factory=lambda: PayloadParam(),
        alias='payloads',
    )
    recover_datas: list[int] = Field(
        default_factory=list,
        alias='recoverDatas',
    )
    work_status: int | None = Field(
        default=None,
        alias='workStatus',
    )
    m_point: Vector3 | None = Field(
        default=None,
        alias='mPoint',
    )
    angle: float | None = Field(
        default=None,
        alias='angle',
    )
    speed: float | None = Field(
        default=None,
        alias='speed',
    )
    type: int = Field(
        default=0,
        alias='type',
    )
    script_vo: list[ScriptVo] | None = Field(
        default=None,
        alias='scriptVo',
    )
    vip: bool = Field(
        default=False,
        alias='vip',
    )
    standard: bool = Field(
        default=False,
        alias='standard',
    )
    next_orbit_mane_time_mills: int = Field(
        default=0,
        alias='nextOrbitManeTimeMills',
    )
    next_orbit_mane_time: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '1970-01-01T00:00:00+00:00'
        ),
        alias='nextOrbitManeTime',
        json_schema_extra={"readOnly": True},
    )


class SimPointThree(CSharpDtoModel):
    """Serialized LJ.DTO.Engine.SimPointThree properties."""

    position: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='position',
    )
    time: str = Field(
        default='',
        alias='time',
    )


class PlatEvent(CSharpDtoModel):
    """Serialized LJ.DTO.Engine.PlatEvent properties."""

    event_type: int = Field(
        default=0,
        alias='eventType',
    )
    event_id: int = Field(
        default=0,
        alias='eventID',
    )
    mission_id: int | None = Field(
        default=None,
        alias='missionID',
    )
    event_time: int = Field(
        default=0,
        alias='eventTime',
    )
    event_end_time: int | None = Field(
        default=None,
        alias='eventEndTime',
    )
    cause_eid: int = Field(
        default=0,
        alias='causeEID',
    )
    target_eid: int | None = Field(
        default=None,
        alias='targetEID',
    )
    event_name: str | None = Field(
        default=None,
        alias='eventName',
    )
    event_phase: int | None = Field(
        default=None,
        alias='eventPhase',
    )
    event_state: int | None = Field(
        default=None,
        alias='eventState',
    )
    event_content: Base64Bytes | None = Field(
        default=None,
        alias='eventContent',
    )
    task_id: int | None = Field(
        default=None,
        alias='taskID',
    )


class SimData(CSharpDtoModel):
    """Serialized LJ.DTO.Engine.SimData properties."""

    scene_id: int = Field(
        default=0,
        alias='sceneId',
    )
    timestamp: int = Field(
        default=0,
        alias='timestamp',
    )
    bjt: datetime = Field(
        default_factory=lambda: datetime.fromisoformat(
            '1970-01-01T08:00:00+08:00'
        ),
        alias='bjt',
        json_schema_extra={"readOnly": True},
    )
    data: dict[str, SimSatSimulation] = Field(
        default_factory=dict,
        alias='data',
    )
    sun_pos_and_vel: Vector6 = Field(
        default_factory=lambda: Vector6([0, 0, 0, 0, 0, 0]),
        alias='sunPosAndVel',
    )
    sun_position: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='sunPosition',
        json_schema_extra={"readOnly": True},
    )
    moon_position: SimPointThree = Field(
        default_factory=lambda: SimPointThree(),
        alias='moonPosition',
    )
    earth_spain_angle: float = Field(
        default=0,
        alias='earthSpainAngle',
    )
    platform_event: list[PlatEvent] = Field(
        default_factory=list,
        alias='platformEvent',
    )
    simulation_speed: int = Field(
        default=0,
        alias='simulationSpeed',
    )
    speed: int | None = Field(
        default=None,
        alias='speed',
    )
    step: float | None = Field(
        default=None,
        alias='step',
    )
    sun_velocity: Vector3 = Field(
        default_factory=lambda: Vector3([0, 0, 0]),
        alias='sunVelocity',
        json_schema_extra={"readOnly": True},
    )
    task_id: str = Field(
        default='',
        alias='taskId',
    )


__all__ = [
    "SpaceWeatherContainer",
    "ScenarioWeather",
    "EnvironmentConfig",
    "EquipmentState",
    "PayloadCcsPayParam",
    "EquipmentUnit",
    "OrbitElements",
    "ForceModel",
    "MassArea",
    "Attitude",
    "Capability",
    "ManeuverCapability",
    "InformationCapability",
    "PerceptionCapability",
    "PlatParam",
    "LaserPayloadParam",
    "DnPayloadParam",
    "ControlledPayloadParam",
    "InterferencePayloadParam",
    "RadarPayloadParam",
    "CommunicationPayloadParam",
    "InfraredPayloadParam",
    "OpticsPayloadParam",
    "PayloadParam",
    "EquipmentParam",
    "ForceEquipment",
    "ForceConfig",
    "Scenario",
    "ProjectDTO",
    "ScriptVo",
    "SimSatSimulation",
    "SimPointThree",
    "PlatEvent",
    "SimData",
]

# Resolve recursive equipment and cross-model references.
for _model_name in __all__:
    globals()[_model_name].model_rebuild()
