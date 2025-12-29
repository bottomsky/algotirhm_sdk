# HTTP 启动与路由（TODO List）

目标：算法开发者可以通过 `from algo_sdk.http import server; server.run()` 一键启动 HTTP 服务。

## A. 服务启动入口

- [x] 新增 `algo_sdk/http/server.py`
  - [x] `run()`：默认读取环境变量并启动服务
  - [x] `create_app()`：返回 ASGI app 供外部框架集成
  - [x] `load_modules(modules: list[str])`：导入算法模块触发注册
- [x] 新增类式 API `Server.run()`（语义与 `server.run()` 一致）

## B. 配置与环境变量

- [x] 读取环境变量：
  - [x] `ALGO_MODULES`（逗号分隔模块路径）
  - [x] `SERVICE_HOST` / `SERVICE_PORT`
  - [x] `EXECUTOR_GLOBAL_MAX_WORKERS`
  - [x] `EXECUTOR_GLOBAL_QUEUE_SIZE`
  - [x] `EXECUTOR_DEFAULT_TIMEOUT_S`
  - [x] `EXECUTOR_KILL_TREE` / `EXECUTOR_KILL_GRACE_S`
- [x] 更新 `.env.example` 与文档说明

## C. 路由设计（FastAPI/ASGI）

- [x] `POST /algorithms/{name}/{version}`：执行算法
- [x] `GET /algorithms`：算法清单
- [x] `GET /algorithms/{name}/{version}/schema`：输入/输出 schema
- [x] `GET /healthz`：存活探针
- [x] `GET /readyz`：就绪探针
- [x] `GET /metrics`：Prometheus 指标输出

## D. 观测与执行器接入

- [x] 默认 `DispatchingExecutor`（支持硬超时）
- [x] 绑定 `InMemoryMetrics` / `InMemoryTracer` 的 observation hooks
- [x] `execution_mode=IN_PROCESS` 算法路由到 `InProcessExecutor`

## E. 测试与示例

- [x] 启动测试：`server.run()` 可在最小配置下启动
- [x] 路由测试：`/algorithms`、`/schema`、`/healthz`、`/readyz`、`/metrics`
- [x] 端到端：加载模块 + 调用算法成功
