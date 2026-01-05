from __future__ import annotations

from algo_dto.base import SimTime
from algo_dto.dto import PrepareRequest, PrepareResult, PrepareResultItem
from algo_sdk import Algorithm, BaseAlgorithm
from algo_sdk.core import AlgorithmType, LoggingConfig
from algo_sdk.runtime import (
    set_response_code,
    set_response_context,
    set_response_message,
)


@Algorithm(
    name="Prepare",
    version="v1",
    description="Prepare algorithm sample implementation.",
    algorithm_type=AlgorithmType.PREPARE,
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class PrepareAlgorithm(BaseAlgorithm[PrepareRequest, PrepareResult]):
    def run(self, req: PrepareRequest) -> PrepareResult:
        set_response_code(2001)
        set_response_message("prepare ok")
        set_response_context(
            {
                "traceId": "trace-prepare",
                "extra": {
                    "source": "prepare",
                    "mode": "test",
                },
            }
        )

        _ = req
        item = PrepareResultItem(
            sat_id=1,
            start_time=SimTime([2025, 1, 1, 0, 0, 0]),
            end_time=SimTime([2025, 1, 1, 0, 10, 0]),
            task_id="task-001",
            sub_task_id="sub-001",
            task_mode=1,
        )

        return PrepareResult(root={"task-001": item})
