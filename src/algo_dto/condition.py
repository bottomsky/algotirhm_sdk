"""行为树条件算法示例的业务输入输出。"""

from __future__ import annotations

from pydantic import AliasChoices, Field, RootModel

from algo_dto.base import CamelBaseModel
from algo_dto.csharp_models import ProjectDTO, SimData, SimSatSimulation


class ConditionSatelliteState(SimSatSimulation):
    """完整 C# 卫星状态；条件示例使用的两个判断字段仍为必填。"""

    # Pydantic supports making inherited defaulted fields required.
    force_type: int = Field(  # pyright: ignore[reportGeneralTypeIssues]
        description="卫星所属阵营"
    )
    is_sat_fault: int = Field(  # pyright: ignore[reportGeneralTypeIssues]
        description="卫星故障标志，1 表示故障"
    )


class ConditionFrameData(SimData):
    """完整 C# 当前帧；data 的键为卫星 ID。"""

    # Preserve the condition endpoint's existing required-field contract.
    data: dict[  # pyright: ignore[reportGeneralTypeIssues]
        str, ConditionSatelliteState
    ]


class ConditionRequest(CamelBaseModel):
    """通过 SDK 标准请求的 data 字段传输的条件算法输入。"""

    frame_data: ConditionFrameData
    project_dto: ProjectDTO = Field(
        description="项目上下文，本示例接收但不参与判断"
    )
    force_type: int = Field(description="当前行为树所属阵营")
    sat_id: str = Field(
        default="",
        validation_alias=AliasChoices("satId", "sateId"),
        description="当前行为树卫星标识，沿用黑板字符串，未提供时为空",
    )


class ConditionResult(RootModel[bool]):
    """条件结果，序列化为 JSON 布尔值，不增加对象包装。"""
