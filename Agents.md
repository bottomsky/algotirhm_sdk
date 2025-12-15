# 算法核心服务 + SDK 设计方案（当前版本）

## 概述
- 目标：通过 `@Algorithm` 装饰器注册算法（函数/类），自动暴露为 HTTP 接口；统一输入/输出协议与生命周期，提供可观测性与（可选）服务注册。
- 关键能力：标准协议封装、进程隔离执行（全局共享池/算法独立池）、结构化异常与崩溃日志、Metrics/Tracing/Health 探针、FastAPI 应用工厂、Consul 注册（可选）。

## 技术栈
- 语言与运行时：`Python 3.13`
- Web 框架：`FastAPI`（应用工厂与路由）
- 模型与校验：`Pydantic`（统一输入/输出模型）
- 服务启动：`uvicorn`
- 并发与隔离：`multiprocessing`（进程池/worker）
- 日志：`logging.QueueHandler`/`QueueListener`（多进程日志汇聚）
- 可观测性：Health（`/healthz`、`/readyz`）、Metrics、Tracing
- 服务注册（可选）：`Consul`

## 项目结构（设计）
```text
algo-platform/
├─ algo_sdk/                 # 提供给算法开发者使用的 SDK
│  ├─ protocol/              # 标准输入输出协议
│  ├─ core/                  # 抽象接口与默认实现（Model/Spec/Registry/AppFactory/Errors）
│  ├─ decorators/            # @Algorithm 装饰器
│  ├─ http/                  # 对外 API Envelope
│  ├─ config/                # SDK 配置（如错误码策略）
│  ├─ runtime/               # 执行运行时（生命周期/进程池/worker）
│  ├─ logging/               # 日志模块（结构化异常/崩溃）
│  ├─ observability/         # 观测模块（metrics/tracing/health）
│  ├─ service_registry/      # 服务注册（Consul）
│  └─ utils/                 # 通用工具
└─ algo_core_service/        # 实际部署的算法核心服务工程
   ├─ main.py                # 加载算法 + 启动服务
   ├─ settings.py            # 服务级配置（端口/模块/执行器等）
   └─ algorithms/            # 示例算法集合
```

## 关键模块说明
- `core`：模型抽象、算法元数据、注册中心、应用工厂、错误结构与异常。
- `decorators`：`@Algorithm` 默认实现，支持函数或类（`run` 方法）。
- `http`：统一的 `api_success`/`api_error` 响应封装。
- `runtime`：`IAlgorithm` 生命周期（`initialize/run/after_run/shutdown`）、执行器（进程池/超时/并发）。
- `observability`：Metrics、Tracing、Health（就绪/存活）。
- `logging`：结构化异常日志与崩溃事件记录（多进程汇聚）。
- `service_registry`：按环境变量开关对接 Consul 服务注册。

## HTTP 接口
- `GET /algorithms`：算法清单（名称/版本/描述/执行策略等）。
- `GET /healthz`：存活探针（HTTP 服务可响应即为存活）。
- `GET /readyz`：就绪探针（算法加载完成、执行器启动等）。
- `GET /algorithms/{name}/{version}/schema`：算法输入/输出 Schema。

## 标准协议
- 请求结构：`{ requestId, datetime, context, data }`
- 响应结构：`{ code, message, requestId, datetime, context, data }`
- 上下文模型：
```python
from pydantic import BaseModel
from typing import Any, Dict

class AlgorithmContext(BaseModel):
    traceId: str | None = None
    tenantId: str | None = None
    userId: str | None = None
    extra: Dict[str, Any] = {}
```

## 运行时与执行器
- 进程池策略：
  - 全局共享池（默认）：资源复用、轻量通用。
  - 算法独立池（`execution.isolated_pool=True`）：适合 GPU/大模型/初始化昂贵算法。
- 执行元数据：`max_workers`、`timeout_s`、`gpu` 等（期望策略，由执行器解释与约束）。

## 服务配置（`algo_core_service/settings.py`）
- `ALGO_MODULES`：要加载的算法模块列表（逗号分隔）。
- `SERVICE_HOST`、`SERVICE_PORT`：服务监听地址与端口。
- `EXECUTOR_GLOBAL_MAX_WORKERS`：全局执行器最大并发。
- `EXECUTOR_DEFAULT_TIMEOUT_S`：默认运行超时秒数。
- `SERVICE_REGISTRY_ENABLED`、`CONSUL_HTTP_ADDR`、`SERVICE_NAME`：服务注册配置。

## 示例算法（函数式与类式）
```python
# 假设来自 algo_sdk
from algo_sdk.core.base_model_impl import BaseModel
from algo_sdk.decorators.algorithm_decorator_impl import DefaultAlgorithmDecorator as Algorithm

class OrbitReq(BaseModel):
    # 输入模型字段定义
    a: float
    e: float

class OrbitResp(BaseModel):
    # 输出模型字段定义
    period_s: float

@Algorithm(name="orbit_propagation", version="v1", description="轨道周期计算")
def orbit_fn(req: OrbitReq) -> OrbitResp:
    """
    计算轨道周期（函数式算法）
    参数:
      - req: 输入模型 OrbitReq，包含半长轴 a、偏心率 e
    返回:
      - OrbitResp: 输出模型，包含周期秒数 period_s
    异常:
      - ValueError: 当输入不合法（如 a <= 0）
    """
    if req.a <= 0:
        raise ValueError("semi-major axis must be positive")
    period = 2 * 3.1415926 * (req.a ** 1.5)  # 简化示例
    return OrbitResp(period_s=period)

@Algorithm(name="orbit_propagation", version="v2", description="轨道周期计算（类式）",
           execution={"isolated_pool": True, "max_workers": 2, "timeout_s": 300})
class OrbitAlgo:
    def initialize(self) -> None:
        """
        算法初始化（可选）
        参数: 无
        返回: None
        异常: RuntimeError 及其子类表示初始化失败
        """
        pass

    def run(self, req: OrbitReq) -> OrbitResp:
        """
        计算轨道周期（类式算法）
        参数:
          - req: 输入模型 OrbitReq
        返回:
          - OrbitResp: 输出模型
        异常:
          - ValueError: 当输入不合法
        """
        if req.a <= 0:
            raise ValueError("semi-major axis must be positive")
        period = 2 * 3.1415926 * (req.a ** 1.5)
        return OrbitResp(period_s=period)

    def after_run(self) -> None:
        """
        单次运行后的清理（可选）
        参数: 无
        返回: None
        异常: 无
        """
        pass

    def shutdown(self) -> None:
        """
        算法关闭清理（可选）
        参数: 无
        返回: None
        异常: 无
        """
        pass
```

## 观测与治理
- 结构化异常日志：记录 `requestId/datetime/algoName/version/entrypointRef/errorType/message/stack/pid` 等。
- 崩溃事件：父进程监控并记录 worker 退出码与上下文。
- Metrics：请求总数/失败数/延迟直方图/队列长度/worker 存活数（按算法维度标签）。
- Tracing：`traceId` 透传与日志关联。
- Health：`/healthz` 存活、`/readyz` 就绪。

## 服务注册（可选 Consul）
- 环境变量：
  - `SERVICE_REGISTRY_ENABLED=true/false`
  - `CONSUL_HTTP_ADDR=http://127.0.0.1:8500`
  - `SERVICE_NAME=algo-core-service`
- 建议在 KV 写入算法清单入口 URL（`/algorithms`）与 Schema URL（`/algorithms/{name}/{version}/schema`）。

## 部署指南
- 本地启动（示例）：`uvicorn algo_core_service.main:app --host 0.0.0.0 --port 8000`
- K8s/容器化：接入 `readinessProbe` 与 `livenessProbe` 指向 `/readyz`、`/healthz`。
- 生产建议：开启结构化日志与 Metrics 抓取；按需启用 Consul 服务注册。

## 测试策略（建议）
- 单元测试：算法函数/类的 `run` 与模型校验；异常路径覆盖。
- 集成测试：HTTP 路由 `/algorithms`、`/schema`、`/readyz`；执行器并发与超时。
- 端到端：加载真实算法模块、校验协议兼容与上下文透传。

## 环境变量（汇总）
- `ALGO_MODULES`、`SERVICE_HOST`、`SERVICE_PORT`
- `EXECUTOR_GLOBAL_MAX_WORKERS`、`EXECUTOR_DEFAULT_TIMEOUT_S`
- `SERVICE_REGISTRY_ENABLED`、`CONSUL_HTTP_ADDR`、`SERVICE_NAME`

## 常见问题
- 算法未找到：检查注册名与版本是否一致，确认模块已被导入（参考 `ALGO_MODULES`）。
- 就绪失败：查看 `/readyz` 返回负载，确认算法加载与执行器启动状态。
- Worker 崩溃：检查结构化异常日志与退出码；必要时启用独立池隔离资源。

## 参考资源
- 设计文档：`docs/algo_core_design.md`

## 变更日志
- v1.0.0（设计稿）：完成核心抽象与默认实现的设计，定义统一协议与运行时模型。
