"""检测当前帧是否存在己方故障卫星的条件算法示例。"""

from __future__ import annotations

from algo_dto.condition import ConditionRequest, ConditionResult
from algo_sdk import Algorithm, BaseAlgorithm, ExecutionMode
from algo_sdk.core import AlgorithmType


@Algorithm(
    name="Condition",
    version="v1",
    description="检测当前帧中是否存在己方故障卫星。",
    algorithm_type=AlgorithmType.CONDITION,
    created_time="2026-11-13",
    author="algo-team",
    category="BehaviorTree",
    application_scenarios="行为树条件节点示例",
    extra={"owner": "algo-core-service"},
    execution={"execution_mode": ExecutionMode.IN_PROCESS},
)
class ConditionAlgorithm(BaseAlgorithm[ConditionRequest, ConditionResult]):
    def run(self, req: ConditionRequest) -> ConditionResult:
        """判断己方是否存在故障卫星。

        参数:
          - req: 当前帧、项目上下文和当前阵营。
        返回:
          - 同阵营卫星中存在 is_sat_fault == 1 时为 true，否则为 false。
        异常:
          - 无显式异常；输入校验由 SDK 统一处理。
        """
        return ConditionResult(
            root=any(
                satellite.force_type == req.force_type
                and satellite.is_sat_fault == 1
                for satellite in req.frame_data.data.values()
            )
        )
