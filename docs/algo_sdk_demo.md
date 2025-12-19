# 算法 SDK 演示说明

这份文档用于下午演示，涵盖 SDK 的设计逻辑、使用方式、当前版本简化点与已实现特性。

## 设计逻辑（从算法到服务）

1. **算法注册**：用 `@Algorithm` 装饰器把函数/类注册为算法，自动生成 `AlgorithmSpec`。
2. **统一协议**：HTTP 层使用 `AlgorithmRequest/AlgorithmResponse`，数据模型统一由 `BaseModel` 校验。
3. **执行调度**：`ExecutorProtocol` 承担隔离/超时/并发策略，默认使用共享池或独立池。
4. **运行时透传**：`AlgorithmContext`、`request_id`、`trace_id` 通过 runtime 上下文传入算法执行体。
5. **观测**：结构化日志 + InMemory Metrics/Tracing，可输出 Prometheus/OTel 格式。

核心模块关系（简化）：

```
算法代码 (@Algorithm) -> AlgorithmRegistry
                 -> AlgorithmHttpService -> Executor -> AlgorithmLifecycle
                                           -> runtime context + observability
```

## 使用方式（最小可运行示例）

### 1) 定义模型与算法

```python
from algo_sdk.core import BaseModel
from algo_sdk.decorators import Algorithm


class OrbitReq(BaseModel):
    a: float
    e: float


class OrbitResp(BaseModel):
    period_s: float


@Algorithm(name="orbit", version="v1", description="轨道周期计算")
def orbit_fn(req: OrbitReq) -> OrbitResp:
    if req.a <= 0:
        raise ValueError("semi-major axis must be positive")
    period = 2 * 3.1415926 * (req.a ** 1.5)
    return OrbitResp(period_s=period)
```

### 2) 构建服务并调用

```python
from datetime import datetime, timezone

from algo_sdk.core import get_registry, InProcessExecutor
from algo_sdk.http import AlgorithmHttpService
from algo_sdk.observability import (
    InMemoryMetrics,
    InMemoryTracer,
    create_observation_hooks,
)
from algo_sdk.protocol.models import AlgorithmContext, AlgorithmRequest

registry = get_registry()

metrics = InMemoryMetrics()
tracer = InMemoryTracer()
hooks = create_observation_hooks(metrics, tracer)

service = AlgorithmHttpService(
    registry,
    executor=InProcessExecutor(),
    observation=hooks,
)

request = AlgorithmRequest(
    requestId="req-1",
    datetime=datetime.now(timezone.utc),
    context=AlgorithmContext(traceId="trace-1", tenantId="tenant-a"),
    data={"a": 7000, "e": 0.01},
)

response = service.invoke("orbit", "v1", request)
print(response.code, response.data)
```

### 3) 在算法内读取上下文

```python
from algo_sdk.runtime import (
    get_current_context,
    get_current_request_id,
    get_current_trace_id,
)


def orbit_fn(req: OrbitReq) -> OrbitResp:
    trace_id = get_current_trace_id()
    request_id = get_current_request_id()
    context = get_current_context()
    # 可用于日志关联/多租户处理
    ...
```

### 4) 输出 Metrics（Prometheus/OTel）

```python
prom_text = metrics.render_prometheus_text()
otel_payload = metrics.build_otel_metrics()
```

## 已简化的内容（当前版本范围）

- **无 FastAPI App Factory**：当前演示使用 `AlgorithmHttpService`，尚未提供默认 HTTP 路由工厂。
- **无健康探针/服务注册**：`/healthz`、Consul 等未接入。
- **Metrics/Tracing 为 InMemory**：已提供 Prometheus/OTel 输出，但未直接暴露 HTTP `/metrics`。
- **超时/崩溃治理为基础版本**：超时为软取消，worker 崩溃检测尚未实现。

## 已实现的特性（可演示）

- 函数/类算法统一注册（`@Algorithm` + `AlgorithmSpec`）
- 统一输入/输出协议与 Pydantic 校验
- 执行器：InProcess、ProcessPool、IsolatedPool、Dispatching
- 执行上下文透传：`request_id/trace_id/tenant/user`
- 结构化日志 + Metrics/Tracing 基础实现
- Prometheus 文本与 OTel JSON 输出

## 演示建议流程

1. 展示算法注册与模型定义（强调强类型/统一协议）。
2. 演示服务调用（`AlgorithmHttpService` + `AlgorithmRequest`）。
3. 演示上下文透传（在算法内读取 `trace_id`/`tenant`）。
4. 演示 Metrics 输出（Prometheus 文本/OTel JSON）。

如需补充 FastAPI 路由或 `/metrics` 端点，可在演示后作为下一阶段计划提出。
