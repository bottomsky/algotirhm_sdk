# ExecutorProtocol 未完成项清单

本文汇总 `src/algo_sdk/core/executor.py` 相对于设计稿 `docs/executorprotocol_develop.md` 的待开发内容，供后续迭代跟踪。

## 核心缺口（按优先级建议）

1. **可观测性**
   - 结构化日志：写入 `requestId/traceId/algo/version/worker_pid/duration_ms/status/error_type`。
   - Metrics：请求总数/失败数、延迟直方图、队列长度、活跃 worker 数（按算法标签）。
   - Tracing：为每次执行建立 span，附带 `algo/version/status/queue_wait/duration`。

2. **上下文透传**
   - `ExecutionRequest` 的 `trace_id/context/request_id` 未进入执行路径与日志/Tracing。
   - worker 侧错误/日志缺少 `AlgorithmContext` 关联信息。

3. **超时/取消与崩溃治理**
   - 进程池超时仅 `future.cancel()`，无法终止已运行的 worker。
   - 缺少超时事件记录与 worker 崩溃检测/重建。
   - 未对超时做明确的恢复策略（重试/降级/阻断）。

4. **健康与容量信号**
   - 无池状态、容量、活跃 worker、队列压力等指标暴露。
   - `readyz` 所需执行器状态判断逻辑缺失。

5. **执行策略收敛与治理**
   - `timeout_s` 仅覆盖，不做上下限或策略合并。
   - `spec.execution.gpu` 等 hints 未被解释或约束。
   - 缺少拒绝策略（排队超时/按算法维度限流）。

6. **扩展执行器**
   - `MockExecutor` / `NoopExecutor` 未实现。
   - 可选 `ExecutionPolicy`/`ExecutionDispatcher`/`WorkerHandle` 接口未落地。

## 已实现但需补充的细节

- `InProcessExecutor` / `ProcessPoolExecutor` / `IsolatedProcessPoolExecutor` / `DispatchingExecutor`
  - 缺少统一的观测埋点与标准日志结构。
  - 缺少执行队列等待时长统计。
  - 缺少 per-algo 维度的运行态指标上报。

## 建议交付拆分（可选）

1. **观测与日志落地**：先打通日志 + Metrics + Tracing，保证可追踪性。
2. **超时/崩溃治理**：补充 worker 崩溃检测与重建策略。
3. **容量与健康**：补齐执行器状态对外暴露。
4. **策略与扩展执行器**：引入 Mock/Noop 与策略接口。

## 参考

- 设计稿：`docs/executorprotocol_develop.md`
- 当前实现：`src/algo_sdk/core/executor.py`
