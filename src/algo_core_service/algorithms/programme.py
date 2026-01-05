from __future__ import annotations

from datetime import timedelta

from algo_dto.base import SimTime, Vector3
from algo_dto.dto import (
    ControlledData,
    OrbitAng,
    ProgrammeRequest,
    ProgrammeResult,
    ProgrammeResultItem,
)
from algo_sdk import Algorithm, BaseAlgorithm
from algo_sdk.core import AlgorithmType, LoggingConfig
from algo_sdk.runtime import (
    set_response_code,
    set_response_context,
    set_response_message,
)


@Algorithm(
    name="Programme",
    version="v1",
    description="Programme algorithm sample implementation.",
    algorithm_type=AlgorithmType.PROGRAMME,
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class ProgrammeAlgorithm(BaseAlgorithm[ProgrammeRequest, ProgrammeResult]):
    def run(self, req: ProgrammeRequest) -> ProgrammeResult:
        """
        简单规划算法的 Mock 实现
        参数:
          - req: ProgrammeRequest 请求数据，包含卫星状态、规划列表与仿真时间
        返回:
          - ProgrammeResult: 规划结果，包含受控数据、姿态指向与任务信息
        异常:
          - 无显式抛出异常；若入参不合法，Pydantic 将在更外层进行校验抛错
        """
        set_response_code(2001)
        set_response_message("programme ok")

        planning_count = len(req.plannings)
        set_response_context(
            {
                "traceId": "trace-plan",
                "extra": {
                    "source": "programme",
                    "mode": "mock",
                    "planningCount": planning_count,
                },
            }
        )

        items: list[ProgrammeResultItem] = []
        for idx, planning in enumerate(req.plannings):
            window_start: SimTime = planning.task_time_start
            window_end: SimTime = planning.task_time_end
            window_end_plus_10m = SimTime.from_datetime(
                window_end.to_datetime() + timedelta(minutes=10)
            )

            controlled_data: list[ControlledData] = [
                ControlledData(
                    id=f"ctrl-{idx + 1:03d}-001",
                    start_time=window_start,
                    end_time=window_end,
                ),
                ControlledData(
                    id=f"ctrl-{idx + 1:03d}-002",
                    start_time=window_end,
                    end_time=window_end_plus_10m,
                ),
            ]

            orbit_ang: list[OrbitAng] = [
                OrbitAng(
                    id=f"ang-{idx + 1:03d}-001",
                    sim_time=window_start,
                    aim_axis=Vector3.from_values(0.0, 0.0, 1.0),
                )
            ]

            items.append(
                ProgrammeResultItem(
                    sat_id=req.sat.sat_id,
                    sat_type=planning.target.sat_type,
                    task_id=planning.task_id,
                    sub_task_id=planning.sub_task_id,
                    planning_id=planning.planning_id,
                    task_mode=planning.task_mode,
                    controlled_data=controlled_data,
                    orbit_ang=orbit_ang,
                )
            )

        return ProgrammeResult(root=items)
