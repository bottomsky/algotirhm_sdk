from __future__ import annotations

from algo_dto.base import VVLHRV
from algo_dto.dto import (
    PredictionRequest,
    PredictionResult,
    PredictionResultItem,
)
from algo_sdk import Algorithm, BaseAlgorithm
from algo_sdk.core import AlgorithmType, LoggingConfig
from algo_sdk.runtime import (
    set_response_code,
    set_response_context,
    set_response_message,
)


@Algorithm(
    name="Prediction",
    version="v1",
    description="Prediction algorithm sample implementation.",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-06",
    author="algo-team",
    category="Cognitive",
    application_scenarios="demo",
    extra={"owner": "algo-core-service"},
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class PredictionAlgorithm(BaseAlgorithm[PredictionRequest, PredictionResult]):
    def run(self, req: PredictionRequest) -> PredictionResult:
        """
        简单预测算法的 Mock 实现
        参数:
          - req: PredictionRequest 请求数据，包含当前卫星状态、目标卫星集合、仿真时间与持续时长
        返回:
          - PredictionResult: 预测结果列表，每项包含最近距离、相对状态（VVLH rv）、评分与最近时间
        异常:
          - 无显式抛出异常；若入参不合法，Pydantic 将在更外层进行校验抛错
        """
        set_response_code(2001)
        set_response_message("predict ok")
        set_response_context(
            {
                "traceId": "trace-predict",
                "extra": {
                    "source": "predict",
                    "mode": "mock",
                    "targetCount": len(req.target_sats),
                },
            }
        )

        # 生成两条示例结果项
        items: list[PredictionResultItem] = [
            PredictionResultItem(
                sat_id=1,
                min_distance=123.45,
                relative_state_vvlh=VVLHRV.from_values(
                    0.0, 0.5, 1.0, 0.01, -0.02, 0.03
                ),
                score=0.95,
                t_nearest_time=req.sim_time,
            ),
            PredictionResultItem(
                sat_id=2,
                min_distance=67.89,
                relative_state_vvlh=VVLHRV.from_values(
                    -0.3, 0.2, 0.8, 0.00, 0.01, -0.02
                ),
                score=0.85,
                t_nearest_time=req.sim_time,
            ),
        ]

        # 返回 RootModel[list[PredictionResultItem]]
        return PredictionResult(root=items)
