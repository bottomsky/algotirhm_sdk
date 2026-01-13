from __future__ import annotations

import os
from typing import Any

import httpx

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


def _read_httpx_test_url() -> str:
    """
    读取 httpx 测试算法使用的外部访问 URL
    参数:
      - 无
    返回:
      - str: 外部访问 URL
    异常:
      - 无；若环境变量不存在则返回默认 URL
    """
    return os.getenv("HTTPX_TEST_URL", "https://httpbin.org/get")


def _coerce_timeout_s(duration_s: float) -> float:
    """
    将入参 duration_s 约束为可用的 httpx 超时时间
    参数:
      - duration_s: float，来自 PredictionRequest 的 duration_s
    返回:
      - float: 约束后的超时时间（单位秒）
    异常:
      - 无；对非正数做默认兜底
    """
    if duration_s <= 0:
        return 5.0
    return min(duration_s, 30.0)


def _http_get_json(
    url: str, timeout_s: float
) -> tuple[int, Any, float | None]:
    """
    使用 httpx 访问外部 URL 并尝试解析 JSON
    参数:
      - url: str，访问目标 URL
      - timeout_s: float，请求超时时间（秒）
    返回:
      - tuple[int, Any, float | None]:
          - status_code: HTTP 状态码
          - payload: JSON 解析结果（失败时为 None）
          - elapsed_ms: 耗时毫秒（不可用时为 None）
    异常:
      - httpx.HTTPError: 网络层错误、超时等
    """
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        resp = client.post(url, json={"sim_time": 123456.789})
        elapsed_ms: float | None = None
        if resp.elapsed is not None:
            elapsed_ms = resp.elapsed.total_seconds() * 1000.0
        payload: Any = None
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        return resp.status_code, payload, elapsed_ms


@Algorithm(
    name="HttpxTest",
    version="v1",
    description="HTTPX external connectivity test algorithm.",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-13",
    author="algo-team",
    category="Diagnostics",
    application_scenarios="demo",
    extra={"owner": "algo-core-service"},
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class HttpxTestAlgorithm(BaseAlgorithm[PredictionRequest, PredictionResult]):
    def run(self, req: PredictionRequest) -> PredictionResult:
        """
        使用 httpx 发起外部 HTTP 请求并返回可观测的测试结果
        参数:
          - req: PredictionRequest，包含 sim_time 与 duration_s 等字段
        返回:
          - PredictionResult: 预测结果列表（单条），用于承载连通性结果摘要
        异常:
          - httpx.HTTPError: 当外部访问失败、超时或网络异常时抛出
        """
        url = _read_httpx_test_url()
        timeout_s = _coerce_timeout_s(req.duration_s)
        status_code, payload, elapsed_ms = _http_get_json(url, timeout_s)

        set_response_code(2001)
        set_response_message("httpx ok")
        set_response_context(
            {
                "traceId": "trace-httpx-test",
                "extra": {
                    "url": url,
                    "statusCode": status_code,
                    "elapsedMs": elapsed_ms,
                    "hasJson": payload is not None,
                },
            }
        )

        item = PredictionResultItem(
            sat_id=0,
            min_distance=float(status_code),
            relative_state_vvlh=VVLHRV.from_values(
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            ),
            score=1.0 if 200 <= status_code < 300 else 0.0,
            t_nearest_time=req.sim_time,
        )

        return PredictionResult(root=[item])
