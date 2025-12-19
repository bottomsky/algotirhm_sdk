# ExecutorProtocol 未完成项清单

本文汇总 `src/algo_sdk/core/executor.py` 相对于设计稿 `docs/executorprotocol_develop.md` 的待开发内容，供后续迭代跟踪。

## 核心缺口（按优先级建议）

1. **可观测性**
   - [x] 结构化日志：写入 `requestId/traceId/algo/version/worker_pid/duration_ms/status/error_type`。
   - [x] Metrics 基础实现：请求总数/失败数、延迟直方图、队列等待直方图（见 `src/algo_sdk/observability/metrics.py`）。
   - [x] Tracing 基础实现：执行 span 与 `queue_wait/duration` 字段（见 `src/algo_sdk/observability/tracing.py`）。
   - [ ] 队列长度、活跃 worker 数等运行态指标仍未实现。

2. **上下文透传**
   - [x] `trace_id/tenant/user` 已进入结构化日志与 tracing span。
   - [ ] 上下文未直接传入算法执行体（如算法内部访问 context）。

3. **超时/取消与崩溃治理**
   - 进程池超时仅 `future.cancel()`，无法终止已运行的 worker。
   - 缺少超时事件记录与 worker 崩溃检测/重建。
   - 未对超时做明确的恢复策略（重试/降级/阻断）。

4. **健康与容量信号**
   - 无池状态、容量、活跃 worker、队列压力等指标暴露。
   - `readyz` 所需执行器状态判断逻辑缺失。

5. **执行策略收敛与治理**
   - [x] `timeout_s` 已做 request/spec 取最小值收敛。
   - [ ] `spec.execution.gpu` 等 hints 未被解释或约束。
   - [ ] 缺少拒绝策略（排队超时/按算法维度限流）。

6. **扩展执行器**
   - `MockExecutor` / `NoopExecutor` 未实现。
   - 可选 `ExecutionPolicy`/`ExecutionDispatcher`/`WorkerHandle` 接口未落地。

## 已实现但需补充的细节

- `InProcessExecutor` / `ProcessPoolExecutor` / `IsolatedProcessPoolExecutor` / `DispatchingExecutor`
  - [x] 统一的结构化日志与队列等待时长统计。
  - [ ] per-algo 维度的运行态指标上报仍需接入到实际监控系统。

## 建议交付拆分（可选）

1. **观测与日志落地**：已完成基础实现（日志 + InMemory Metrics/Tracing）。
2. **超时/崩溃治理**：补充 worker 崩溃检测与重建策略。
3. **容量与健康**：补齐执行器状态对外暴露。
4. **策略与扩展执行器**：引入 Mock/Noop 与策略接口。

## 参考

- 设计稿：`docs/executorprotocol_develop.md`
- 当前实现：`src/algo_sdk/core/executor.py`
