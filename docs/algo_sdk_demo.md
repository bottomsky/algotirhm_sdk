# 算法 SDK 演示说明

本文用于下午演示：介绍我们构建的算法 SDK 的设计逻辑与使用方式，重点展示“统一协议 + 执行器 + 生命周期 + 上下文透传 + 可观测”的闭环。

核心链路（简化）：

```
@Algorithm 注册 -> AlgorithmRegistry/AlgorithmSpec
HTTP 请求(AlgorithmRequest) -> AlgorithmHttpService -> Executor -> 算法（生命周期类）
                                     |-> runtime context
                                     |-> metrics/tracing hooks
```

---

## 第一章：生命周期（解释 BaseAlgorithm 设计）

### 1.1 为什么引入生命周期

现实算法通常不仅是一次函数调用，还需要：初始化（加载模型/连接资源）、每次执行后的清理、服务退出时释放资源。

SDK 用 `AlgorithmLifecycleProtocol` 定义类式算法的标准生命周期：
- `initialize()`：一次性初始化（可选，默认可为空实现）
- `run(req)`：核心执行（必需）
- `after_run()`：每次执行后的回调（可选，默认可为空实现）
- `shutdown()`：资源释放（可选，默认可为空实现）

### 1.2 BaseAlgorithm 的定位与简化点

`BaseAlgorithm` 是一个“少写样板代码”的基类：
- 提供 `initialize/after_run/shutdown` 的默认 no-op 实现，算法开发者只需实现 `run()`。
- 通过抽象方法强制 `run()` 存在，避免生命周期类缺少核心逻辑。
- 仍然遵循 `AlgorithmLifecycleProtocol`，可被执行器统一驱动。

提示：装饰器对“类式算法”的约束是结构化的（Protocol），不强制必须继承 `BaseAlgorithm`；但演示/团队约定建议继承以减少实现成本与保持一致性。

---

## 第二章：如何定义一个算法模型（输入/输出）

### 2.1 BaseModel（统一协议与强校验）

算法的输入/输出模型统一使用 `algo_sdk.core.BaseModel`（Pydantic v2）：
- 禁止多余字段（`extra="forbid"`），避免前后端字段漂移
- 支持严格校验与可预测的序列化（`model_dump()`）

### 2.2 示例：定义请求/响应模型

```python
from algo_sdk.core import BaseModel


class OrbitReq(BaseModel):
    a: float
    e: float


class OrbitResp(BaseModel):
    period_s: float
```

---

## 第三章：如何运行这个模型（HTTP 接入与执行器传递链路）

### 3.1 HTTP 消息接入（统一 Envelope）

SDK 定义统一请求/响应协议：
- 请求：`AlgorithmRequest`（含 `requestId/datetime/context/data`）
- 响应：`AlgorithmResponse`（含 `code/message/requestId/datetime/context/data`）

其中 `context` 使用 `AlgorithmContext`（含 `traceId/tenantId/userId/extra`），执行器会将其透传到算法执行体。

### 3.2 AlgorithmHttpService 的职责（接入层“胶水”）

`AlgorithmHttpService` 是 HTTP 框架与执行器之间的桥接层：
1. 依据 `name/version` 从 `AlgorithmRegistry` 获取 `AlgorithmSpec`
2. 构造 `ExecutionRequest` 并调用 `executor.submit()`
3. 将 `ExecutionResult` 映射为 `AlgorithmResponse`（成功/错误统一封装）
4. 通过 `ObservationHooks` 把观测事件回调出去（metrics/tracing）

### 3.3 执行器如何把消息传递给算法

执行器（`ExecutorProtocol` 的实现）负责把“HTTP 层的 request”变成“算法可执行的调用”：
- 入参 `payload`：支持 dict / BaseModel；执行器会按 `AlgorithmSpec.input_model` 做校验与转换
- 输出 `data`：按 `AlgorithmSpec.output_model` 做校验与转换
- 并发/隔离：可选择本进程/共享进程池/独立池；`DispatchingExecutor` 可根据 `execution.execution_mode` 与 `execution.isolated_pool` 路由
- 上下文透传：在执行前设置 runtime context（`request_id/trace_id/context`），执行后清理
- 状态模式：`execution.stateful=True` 时复用实例（进程内常驻）；默认 `False`（每次请求创建并释放实例）

### 3.4 最小演示：调用一次算法（不依赖 Web 框架）

前提：算法必须已注册到 `AlgorithmRegistry`。最常见的方式是“导入算法模块”，触发 `@Algorithm` 装饰器完成注册。

```python
from datetime import datetime, timezone

from algo_sdk.core import InProcessExecutor, get_registry
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
print(response.code, response.message, response.data)
```

### 3.5 算法如何读取上下文（透传能力）

```python
from algo_sdk.runtime import (
    get_current_context,
    get_current_request_id,
    get_current_trace_id,
)


def orbit_fn(req: OrbitReq) -> OrbitResp:
    trace_id = get_current_trace_id()
    request_id = get_current_request_id()
    tenant_id = get_current_context().tenantId if get_current_context() else None
    ...
```

---

## 第四章：算法如何注册（注册方式与注册内容）

### 4.1 类式算法注册（必须符合 AlgorithmLifecycleProtocol）

```python
from algo_sdk.core import BaseAlgorithm
from algo_sdk.decorators import Algorithm


@Algorithm(
    name="orbit",
    version="v2",
    description="轨道周期计算（类式）",
    execution={
        "stateful": True,
        "isolated_pool": True,
        "max_workers": 2,
        "timeout_s": 30,
    },
)
class OrbitAlgo(BaseAlgorithm[OrbitReq, OrbitResp]):
    def run(self, req: OrbitReq) -> OrbitResp:
        if req.a <= 0:
            raise ValueError("semi-major axis must be positive")
        period = 2 * 3.1415926 * (req.a ** 1.5)
        return OrbitResp(period_s=period)
```

注意（进程池/Windows 兼容性）：
- 当使用 `ProcessPoolExecutor` / `DispatchingExecutor` 等“多进程执行器”时，算法入口（类/函数）以及其输入/输出 `BaseModel` 类型必须是 **可被 pickle 序列化** 的对象。
- 实践约束：请把算法类/函数、以及请求/响应模型 **定义在模块顶层**（可通过 `module.path:SymbolName` 导入），不要定义在函数内部/闭包中，也不要使用 lambda。
- SDK 在 `@Algorithm` 注册时会做一次 pickle 冒烟测试，不满足条件会直接报 `AlgorithmValidationError`，避免运行时在 worker 侧才失败。

### 4.3 注册内容（AlgorithmSpec）包含什么

装饰器会生成 `AlgorithmSpec` 并注册到 `AlgorithmRegistry`，内容包括：
- `name/version/description`
- `input_model/output_model`（用于校验与 schema 输出）
- `execution`：`execution_mode/stateful/isolated_pool/max_workers/timeout_s/gpu`（执行 hints）
- `entrypoint` 与 `is_class`（函数/类入口）

`execution_mode` 使用枚举 `ExecutionMode`，默认 `ExecutionMode.PROCESS_POOL`；需要本进程执行可设置为 `ExecutionMode.IN_PROCESS`。

---

## 第五章：算法服务对外暴露的 HTTP 端口与信息查询

### 5.1 设计目标（规划的默认接口）

按设计稿，算法核心服务建议暴露以下 HTTP 接口：
- `GET /algorithms`：算法清单（name/version/description/execution hints）
- `GET /algorithms/{name}/{version}/schema`：输入/输出 schema（便于联调与自动化）
- `GET /healthz`：存活探针（HTTP 可响应即存活）
- `GET /readyz`：就绪探针（算法加载完成、执行器可用等）
- `GET /metrics`：Prometheus 指标（可选）

### 5.2 当前版本实现状态（避免演示误解）

本仓库当前实现到“接入层 + 执行器 + 协议”，但尚未提供默认 FastAPI app/router：
- 已有：`AlgorithmHttpService`（可嵌入任意 HTTP 框架），以及 `AlgorithmRequest/AlgorithmResponse` 协议模型
- 已有：Metrics 输出 `InMemoryMetrics.render_prometheus_text()` / OTel JSON `build_otel_metrics()`（可直接作为 `/metrics` 响应体）
- 未内置：`/algorithms`、`/schema`、`/healthz`、`/readyz` 的 FastAPI 路由实现（属于下一阶段集成工作）

---

## 当前版本：简化了哪些功能（演示可强调）

- 不提供默认 FastAPI App Factory（演示用 `AlgorithmHttpService` 直接体现链路）
- 未集成健康探针与服务注册（Consul/K8s readiness/liveness）
- Metrics/Tracing 采用 InMemory 记录器（输出格式已具备，但未内置 HTTP 端点）
- 进程池超时为基础版本（软取消），worker 崩溃检测/重建尚未实现
- 版本变更：从 `0.2.0` 起，类式算法默认 `execution.stateful=False`（每次请求创建并释放实例）

## 当前版本：有哪些特性（演示可落地）

- 算法注册：仅支持类式算法（需符合生命周期协议）
- 输入/输出强类型 + Pydantic 校验
- 执行器策略：本进程/共享进程池/独立池/自动路由
- 上下文透传：算法内部可读取 `request_id/trace_id/tenant/user`
- 结构化日志 + Metrics/Tracing（含 Prometheus/OTel 输出）

说明：如果确实需要“函数式算法”体验，可以通过封装一个生命周期类，在 `run()` 内调用函数逻辑；后续也可以把装饰器扩展回“函数/类两种模式”。

---

## 第六章：计算架构（有状态/共享进程池/独立进程池）

本章解释运行时“计算架构”的几个关键概念，以及它们在当前 SDK 中如何落地。

### 6.1 一次 work 是什么

在 SDK 里，一次 work 可以理解为“一次算法调用请求”：
- 输入：`ExecutionRequest`（包含 `spec + payload + request_id/context/trace`）
- 输出：`ExecutionResult`（包含 `success/data/error + timing/worker_pid`）

### 6.2 共享进程池（Shared Pool）

**定义**：多个算法共享同一组 worker 进程来执行 work。

**实现**：`ProcessPoolExecutor` 内部维护一个进程池，并把 `_worker_execute` 作为 worker 侧入口。
为避免无限排队，使用 `BoundedSemaphore` 做简单背压：拿不到 slot 直接返回 `rejected`。

**优点**
- 进程复用、资源利用率高，适合大量轻量算法
- 服务侧管理简单

**缺点**
- 算法之间相互竞争 worker 资源，重型算法会挤占轻量算法吞吐
- 即使“无状态模式”，worker 进程仍会复用，因此进程级缓存/全局变量可能残留

### 6.3 独立进程池（Isolated Pool）

**定义**：每个算法（name+version）单独拥有自己的进程池（worker 集合）。

**实现**：`IsolatedProcessPoolExecutor` 为每个算法维护一个 `ProcessPoolExecutor`；
`DispatchingExecutor` 根据 `spec.execution.isolated_pool` 自动路由到共享池或独立池。

**优点**
- 资源/故障域隔离，适合 GPU/大模型/初始化昂贵算法
- 每个算法可单独设置 `max_workers/timeout_s`

**缺点**
- 进程数量更多，内存占用与管理成本更高

### 6.4 有状态 vs 无状态（算法实例是否复用）

注意：这里的“状态”指**算法实例对象是否跨请求复用**，不是“进程是否复用”。

通过装饰器 `execution.stateful` 控制：
- `stateful=False`（默认，无状态实例）：每个请求都会创建算法实例并执行，结束后立即 `shutdown()` 释放
- `stateful=True`（有状态实例）：进程内缓存算法实例，后续请求复用同一个实例，直到进程退出才释放

**业务建议**
- 需要模型常驻、状态持续（例如加载权重/缓存） → `stateful=True`
- 需要每次请求干净隔离 → `stateful=False`

提示：在进程池场景下，`stateful=True` 的“状态”是“每个 worker 进程一份状态”。如果业务需要“全局唯一状态”，通常需配合 `isolated_pool=True` 且 `max_workers=1`。

---

## 第七章：超时硬处理与资源释放（针对 CPU/GPU 重计算）

本章说明我们如何在现有计算架构下做到“超时即释放资源”。这里的核心原则是：**要可靠释放 CPU/GPU 资源，必须能终止占用资源的 OS 进程**。

### 7.1 两类超时：排队超时 vs 执行超时

- **排队超时（queue timeout）**：请求长时间拿不到 worker（队列压力大），直接返回错误（不涉及资源释放）。
- **执行超时（execution timeout）**：work 已开始运行但超时，必须强制终止执行进程以释放资源（硬超时）。

当前 SDK 使用 `timeout_s` 作为每次调用的超时上限：
- 算法级默认：`execution.timeout_s`
- 请求级覆盖：`ExecutionRequest.timeout_s`
- 生效规则：两者取最小值（如果请求未传，则使用算法默认）

硬超时主要作用在“执行阶段”。

### 7.2 InProcessExecutor 的限制

`InProcessExecutor` 在同一进程内执行 Python 代码，**无法做到可靠硬超时**（无法安全地强杀正在运行的函数而不破坏进程状态）。因此：
- 仅建议用于开发/测试
- 生产如需硬超时，请使用多进程执行器（共享池/独立池）

### 7.3 共享池/独立池如何做到硬超时

为了硬超时，我们采用 **supervised process pool（自管 worker 进程）** 的思想：
- 主进程维护固定数量的 worker 进程（共享池全局 N 个；独立池每算法 N 个）
- 每个 work 都在某个 worker 进程里执行
- 当某个 work 超时：
  - 主进程立刻终止对应 worker 进程（terminate/kill）
  - 标记该请求为超时并返回
  - 拉起新的 worker 进程补位，恢复池容量

这能确保：超时计算占用的 CPU/GPU/内存随进程结束而释放（无需依赖算法自身清理逻辑）。

**进程树终止（可选）**
- 通过执行器构造参数 `kill_tree=True` 开启
- Windows 使用 `taskkill /T /F`，Unix 使用 `setsid + killpg` 终止进程组
- 适合算法内部会派生子进程的场景

### 7.4 有状态/无状态对硬超时的影响

- `stateful=False`（默认）：每次请求创建实例，结束后 `shutdown()`。硬超时 kill 可能来不及跑 `shutdown()`，但进程被终止后资源仍会被 OS 回收。
- `stateful=True`：实例常驻。硬超时 kill 会导致该 worker 进程的常驻状态丢失，重建 worker 后会重新初始化（这是可接受的治理代价）。

提示：如果业务要求“每算法全局唯一状态”，通常需要 `isolated_pool=True` 且 `max_workers=1`，否则会出现“每个 worker 进程一份状态”。

---

## 第八章：HTTP 一键启动设计（面向算法开发者）

目标：让只会写算法的同学最小成本启动 HTTP 服务。

### 8.1 最简使用方式（建议入口）

**算法脚本：**

```python
from algo_sdk.core import BaseAlgorithm, BaseModel
from algo_sdk.decorators import Algorithm


class Req(BaseModel):
    x: int


class Resp(BaseModel):
    y: int


@Algorithm(name="double", version="v1")
class DoubleAlgo(BaseAlgorithm[Req, Resp]):
    def run(self, req: Req) -> Resp:
        return Resp(y=req.x * 2)
```

**启动命令（推荐模块式 API）：**

```bash
set ALGO_MODULES=algo
python -c "from algo_sdk.http import server; server.run()"
```

**启动命令（可选类式 API，规划接口）：**

```bash
set ALGO_MODULES=algo
python -c "from algo_sdk.http import Server; Server.run()"
```

### 8.2 推荐的 `server.run()` 行为

`server.run()` 应该完成以下流程：
1. 读取环境变量（如 `ALGO_MODULES/SERVICE_HOST/SERVICE_PORT/EXECUTOR_*`）
2. 导入算法模块（触发 `@Algorithm` 注册）
3. 创建 `AlgorithmHttpService`（默认 `DispatchingExecutor`）
4. 绑定观测 hooks（metrics/tracing）
5. 构建 HTTP 路由并启动 `uvicorn`

### 8.3 默认路由（规划）

- `POST /algorithms/{name}/{version}`：执行算法
- `GET /algorithms`：算法清单
- `GET /algorithms/{name}/{version}/schema`：输入/输出 schema
- `GET /healthz`：存活探针
- `GET /readyz`：就绪探针
- `GET /metrics`：Prometheus 指标文本

### 8.4 高级用法（可选）

- `server.create_app()`：返回 ASGI app 供二次集成
- `server.run(modules=..., host=..., port=..., executor=...)`：覆盖默认行为

### 8.5 设计原则

- **最小成本**：不要求算法开发者理解 FastAPI/ASGI
- **默认安全**：默认走进程池执行（支持硬超时）
- **可扩展**：支持用户传入 executor 或自定义路由

### 8.6 示例：临时测试 vs 生产启动

**临时测试（不推荐生产）**  
算法脚本中直接启动 HTTP，仅用于本地调试：

```python
from algo_sdk.core import BaseAlgorithm, BaseModel
from algo_sdk.decorators import Algorithm


class Req(BaseModel):
    x: int


class Resp(BaseModel):
    y: int


@Algorithm(name="double", version="v1")
class DoubleAlgo(BaseAlgorithm[Req, Resp]):
    def run(self, req: Req) -> Resp:
        return Resp(y=req.x * 2)


if __name__ == "__main__":
    from algo_sdk.http import Server
    Server.run()
```

**生产推荐方式**  
算法模块只负责定义/注册，HTTP 服务由独立启动脚本负责。

算法模块（`algos.py`）：

```python
from algo_sdk.core import BaseAlgorithm, BaseModel
from algo_sdk.decorators import Algorithm


class Req(BaseModel):
    x: int


class Resp(BaseModel):
    y: int


@Algorithm(name="double", version="v1")
class DoubleAlgo(BaseAlgorithm[Req, Resp]):
    def run(self, req: Req) -> Resp:
        return Resp(y=req.x * 2)
```

服务启动脚本（`run_server.py`）：

```python
import os

from algo_sdk.http import Server

os.environ.setdefault("ALGO_MODULES", "algos")
os.environ.setdefault("SERVICE_HOST", "0.0.0.0")
os.environ.setdefault("SERVICE_PORT", "8000")

Server.run()
```

**同等可行方式：在启动脚本中直接 import 算法模块**

当算法模块数量较少，或你希望明确控制导入顺序时，可以在启动脚本中直接导入算法模块：

```python
# run_server.py
import my_algos  # 触发 @Algorithm 注册
from algo_sdk.http import Server

Server.run()
```

这与配置 `ALGO_MODULES` 的效果等价，但更显式、可控。
