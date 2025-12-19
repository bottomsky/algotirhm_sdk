# 硬超时与资源释放（TODO List）

本文用于跟踪“硬超时 + 资源释放”能力的落地任务，目标是在 CPU/GPU 等高成本计算场景下，超时能够**真正释放资源**（通过终止执行进程并重建 worker）。

## 目标与范围

- 覆盖执行模式：
  - `InProcessExecutor`（明确限制：无法做到可靠硬超时）
  - 共享进程池：`ProcessPoolExecutor`
  - 独立进程池：`IsolatedProcessPoolExecutor`
  - 路由：`DispatchingExecutor`
- 超时类型：
  - 排队超时（可选）：等待 worker 过久直接返回（不涉及资源释放）
  - 执行超时（必须）：已开始执行则终止 worker 进程以释放资源（硬超时）

## 任务清单（按交付顺序）

### A. 协议与配置
- [ ] 明确超时语义：`timeout_s` 是否为端到端（排队+执行）或仅执行超时；默认语义写入文档
- [ ] 增加可选配置（服务级或执行器构造参数）：
  - [ ] `kill_grace_s`：优雅终止等待时间（超时后先 terminate，再 kill）
  - [ ] `hard_timeout_enabled`：是否启用硬超时（生产默认启用）
  - [ ] `kill_tree`（可选）：杀进程树（Windows/Unix 不同实现）

### B. 执行器实现（核心）
- [ ] 设计并实现 supervised pool（自管 worker 进程）：
  - [ ] 固定 worker 数（= max_workers）
  - [ ] worker 状态跟踪：idle/busy、task_id、deadline
  - [ ] 任务分发：按 worker input queue 精确派发
  - [ ] 结果回收：output queue + listener 线程 dispatch 到等待者
  - [ ] 超时处理：超时即终止对应 worker，并拉起新 worker 补位
  - [ ] 崩溃处理：worker 异常退出时，标记当前 task 为 system error，并重建 worker
- [ ] 将 `ProcessPoolExecutor` 从 `concurrent.futures` 升级为 supervised pool 实现
- [ ] `IsolatedProcessPoolExecutor` 复用新的 `ProcessPoolExecutor`（每算法一套）
- [ ] `DispatchingExecutor` 保持路由逻辑不变，仅底层执行器升级

### C. 状态模式与生命周期
- [ ] `execution.stateful=False`（默认）：每次请求创建实例并 `shutdown()`，保证实例级无状态
- [ ] `execution.stateful=True`：进程内缓存实例（有状态），超时 kill worker 会导致状态丢失（可接受并写明）

### D. 观测与可运维性
- [ ] 日志：超时事件记录 `request_id/trace_id/algo/version/worker_pid/timeout_s`
- [ ] Metrics（可选增强）：增加 `worker_kill_total` / `worker_restart_total` / `timeout_total`
- [ ] 健康信号（后续）：连续超时/崩溃触发降级或熔断

### E. 测试策略
- [ ] 共享池执行超时：长 sleep 触发超时，确认返回 `timeout`
- [ ] 超时后可继续执行：下一次请求仍能成功（说明 worker 已重建）
- [ ] 独立池隔离：某算法超时不影响另一个算法成功（需要两个 spec）
- [ ] 有状态/无状态语义：`stateful=True` 复用计数，`stateful=False` 每次归零

## 约束说明

- `InProcessExecutor` 无法可靠硬超时（除非杀掉整个服务进程），仅用于开发/测试。
- 对 GPU 等资源，最可靠的回收方式是终止占用该资源的 OS 进程；因此硬超时的落地必须基于进程隔离执行。

