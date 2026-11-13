from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel as PydanticBaseModel
from pydantic import RootModel, model_serializer

from algo_dto.base import CamelBaseModel
from algo_dto.condition import ConditionResult
from algo_sdk import (
    AlgorithmSpec,
    AlgorithmType,
    BaseAlgorithm,
    ExecutionConfig,
    ExecutionRequest,
    InProcessExecutor,
    LoggingConfig,
    ProcessPoolExecutor,
)
from algo_sdk.logging.impl.standard import (
    JsonFormatter,
    StandardLoggingConfigurator,
)
from algo_sdk.logging.serialization import to_json_value
from algo_sdk.logging.settings import LoggingSettings


class BusinessRequest(CamelBaseModel):
    payload_text: str
    event_time: datetime
    secret_token: str
    nested: list[dict[str, object]]


class BusinessResult(BusinessRequest):
    pass


class EchoAlgorithm(BaseAlgorithm[BusinessRequest, BusinessResult]):
    def run(self, req: BusinessRequest) -> BusinessResult:
        return BusinessResult.model_validate(req.model_dump())


@pytest.mark.parametrize(
    "executor_type", [InProcessExecutor, ProcessPoolExecutor]
)
@pytest.mark.parametrize("max_length", [0, 8])
def test_full_json_payloads_in_files_and_console(
    executor_type, max_length: int, tmp_path: Path
) -> None:
    settings = LoggingSettings(
        error_dir=None,
        payload_dir=str(tmp_path),
        general_dir=None,
        general_enabled=False,
        level=logging.INFO,
        rotate_when="midnight",
        backup_count=1,
        console_enabled=True,
    )
    handlers = StandardLoggingConfigurator(settings)._build_handlers(
        JsonFormatter()
    )
    console = io.StringIO()
    handlers[0].setStream(console)
    logger = logging.getLogger("algo_sdk.core.executor")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    for handler in handlers:
        logger.addHandler(handler)

    text = '完整输出"\\\n' + "卫星数据" * 3000
    event_time = datetime(2026, 11, 13, tzinfo=timezone.utc)
    req = BusinessRequest(
        payload_text=text,
        event_time=event_time,
        secret_token="do-not-log",
        nested=[{"secretToken": "also-private", "enabled": False}],
    )
    spec = AlgorithmSpec(
        name="json-echo",
        version="v1",
        description=None,
        created_time="2026-11-13",
        author="qa",
        category="unit",
        input_model=BusinessRequest,
        output_model=BusinessResult,
        algorithm_type=AlgorithmType.CONDITION,
        execution=ExecutionConfig(),
        entrypoint=EchoAlgorithm,
        is_class=True,
        logging=LoggingConfig(
            enabled=True,
            log_input=True,
            log_output=True,
            max_length=max_length,
            redact_fields=("secret_token",),
        ),
    )
    if executor_type is ProcessPoolExecutor:
        executor = executor_type(max_workers=1)
    else:
        executor = executor_type()
    try:
        result = executor.submit(
            ExecutionRequest(spec=spec, payload=req, request_id="full-json")
        )
        assert result.success, result.error
        assert result.data.secret_token == "do-not-log"
    finally:
        executor.shutdown()
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(previous_level)

    file_lines = (
        (tmp_path / "payload.log").read_text(encoding="utf-8").splitlines()
    )
    console_lines = console.getvalue().splitlines()
    assert len(file_lines) == len(console_lines) == 1
    assert file_lines == console_lines
    record = json.loads(file_lines[0])
    for key in ("input_preview", "output_preview"):
        assert isinstance(record[key], dict)
        assert record[key]["payloadText"] == text
        assert record[key]["eventTime"] == "2026-11-13T00:00:00Z"
        assert record[key]["secretToken"] == "***"
        assert record[key]["nested"] == [
            {"secretToken": "***", "enabled": False}
        ]
    assert "do-not-log" not in file_lines[0]
    assert "also-private" not in file_lines[0]
    assert "...(truncated)" not in file_lines[0]


@pytest.mark.parametrize(
    "output, expected",
    [
        (ConditionResult(root=False), False),
        (RootModel[list[int]](root=[1, 2]), [1, 2]),
        (RootModel[dict[str, int]](root={"1001": 1}), {"1001": 1}),
    ],
)
def test_formatter_preserves_root_model_json(output, expected) -> None:
    record = logging.LogRecord("test", logging.INFO, "", 0, "ok", (), None)
    record.output_preview = output
    payload = json.loads(JsonFormatter().format(record))
    assert payload["output_preview"] == expected
    assert type(payload["output_preview"]) is type(expected)


def test_formatter_handles_nonfinite_numbers_as_json_null() -> None:
    record = logging.LogRecord("test", logging.INFO, "", 0, "ok", (), None)
    record.input_preview = {"value": float("nan")}
    assert json.loads(JsonFormatter().format(record))["input_preview"] == {
        "value": None
    }


def test_broken_serializer_produces_json_error() -> None:
    class BrokenResult(PydanticBaseModel):
        @model_serializer
        def serialize(self):
            raise ValueError("broken serializer")

    value = to_json_value(BrokenResult())
    assert "serialization_error" in value
    assert value["value_type"] == "BrokenResult"
    json.dumps(value, allow_nan=False)
