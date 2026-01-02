from __future__ import annotations

from algo_sdk import Algorithm
from algo_dto.base import SimTime
from algo_dto.dto import PrepareRequest, PrepareResult, PrepareResultItem


@Algorithm(
    name="Prepare",
    version="v1.0.0",
    description="Prepare algorithm sample implementation.",
)
def prepare(req: PrepareRequest) -> PrepareResult:
    item = PrepareResultItem(
        sat_id=1,
        start_time=SimTime([2025, 1, 1, 0, 0, 0]),
        end_time=SimTime([2025, 1, 1, 0, 10, 0]),
        task_id="task-001",
        sub_task_id="sub-001",
        task_mode=1,
    )
    return PrepareResult(root={"task-001": item})
