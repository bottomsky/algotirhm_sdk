# ExecutorProtocol 模块设计稿

## 设计目标
- 作为 HTTP 层与算法运行时的“胶水”，统一入口、统一协议，屏蔽并发/超时/隔离/观测细节。
- 可插拔：支持不同执行策略（本地直跑、线程/进程池、算法独立池、Mock/Noop）而不影响上层 API。
- 可观测：执行全链路日志、Metrics、Tracing、崩溃/超时记录，支持请求上下文透传（traceId/tenant/user）。
- 可治理：基于 AlgorithmSpec.execution（max_workers/timeout_s/isolated_pool/gpu 等）做资源与调度决策，暴露健康与容量信号。

## 角色与主要类型
- `ExecutionRequest`（建议 dataclass）：
  - `spec: AlgorithmSpec`（已含 execution hints）
  - `payload: BaseModel | Mapping[str, Any]`（原始输入或已校验模型）
  - `request_id: str`、`trace_id: str | None`、`context: AlgorithmContext | None`
  - `timeout_s: int | None`（优先使用 spec.execution.timeout_s，显式传入可覆盖但需收敛）
- `ExecutionResult`（建议 dataclass）：
  - `success: bool`
  - `data: BaseModel | None`（算法输出）
  - `error: ExecutionError | None`（标准化错误）
  - `started_at: float`、`ended_at: float`、`worker_pid: int | None`
- `ExecutionError`：`kind`（validation/timeout/rejected/runtime/system），`message`，`details`，`traceback`（可选）。
- `ExecutorProtocol`：
  ```python
  class ExecutorProtocol(Protocol):
      def submit(self, request: ExecutionRequest) -> ExecutionResult: ...
      def start(self) -> None: ...  # 可选，启动池/预热
      def shutdown(self, *, wait: bool = True) -> None: ...
  ```
- 内部可选接口：`WorkerHandle`（进程/线程封装）、`ExecutionDispatcher`（路由到全局池或独立池）、`ExecutionPolicy`（重试/超时策略）。

## 执行流程（同步视角）
1) 入参校验：确认 spec 存在，payload 类型安全（Pydantic 校验），合并 timeout_s。
2) 路由与调度：根据 `spec.execution.isolated_pool` 等选择全局池或算法独立池，按 `max_workers` 做排队/拒绝（队列满可返回 `ExecutionError(kind='rejected')`）。
3) 生命周期驱动：在 worker 内创建/复用算法实例，依次调用 `initialize`（可选，一次性）、`run`、`after_run`，异常按约定捕获。
4) 超时/取消：执行计时，超时触发取消和 `ExecutionError(kind='timeout')`，并记录超时事件。
5) 结果封装：成功时返回 `ExecutionResult(success=True, data=...)`；失败时包装错误，携带 `traceback`（非生产可截断）。
6) 观测与日志：
   - 日志：requestId/traceId/algo/version/worker_pid/duration_ms/status/error_type。
   - Metrics：请求总数、失败数、耗时直方图、队列长度、活动 worker 数（按算法标签）。
   - Tracing：为每次执行创建 span，附上 algo/version/status/queue_wait/duration。
7) 健康与治理：暴露运行时状态（池可用、worker 存活、队列压力），供 `/readyz` 判断；异常频繁时可降级/阻止提交。

## 并发与隔离策略
- **全局池执行器**：默认共享进程池，轻量算法复用资源；受 `EXECUTOR_GLOBAL_MAX_WORKERS` 控制。
- **算法独立池**：针对高资源或长初始化算法，按 `spec.execution.isolated_pool=True` 创建专属进程池，可限流并自定义超时。
- **直跑/同步执行器**：用于本地开发或测试（无需进程池）。
- **Mock/Noop 执行器**：返回固定结果，便于端到端流水线测试。

## 异常与错误映射
- `validation`：入参校验失败（Pydantic/自定义校验）。
- `timeout`：执行超时或获取 worker 超时。
- `rejected`：队列满/资源不足导致未执行。
- `runtime`：算法自身抛出的业务异常。
- `system`：进程崩溃、序列化失败、未知内部错误。
- 映射到 HTTP 层：可转换为统一错误码（如 400/429/500）和 message，日志里保留完整上下文。

## 与 HTTP / SDK 协作
- HTTP 层负责解析请求、构造 `ExecutionRequest` 并调用 `executor.submit`。
- Executor 返回的 `ExecutionResult` 由 HTTP 层封装为标准响应 `{code,message,data,requestId,datetime,context}`。
- 上下文透传：将 `AlgorithmContext` 信息和 traceId 带入日志/Tracing。

## 可扩展实现建议
- `InProcessExecutor`：直接调用算法函数/类；适合单机开发或同步场景。
- `ProcessPoolExecutor`：全局共享池；fork/exec 创建 worker，支持超时与崩溃检测。
- `IsolatedProcessPoolExecutor`：按算法创建独立池，隔离 GPU/大模型。
- `MockExecutor`：返回预置结果；用于无算法依赖的接口联调。

## 测试策略
- 单元：`submit` 入参校验、超时/拒绝分支、错误包装；直跑执行器的算法调用路径。
- 集成：进程池执行、超时触发、崩溃重建、算法生命周期（initialize/after_run/shutdown）。
- 观测：日志字段覆盖、Metrics 标签正确性、Tracing span 生成。
