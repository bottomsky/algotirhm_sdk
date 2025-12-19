from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from ..core.executor import ExecutionRequest, ExecutionResult

DEFAULT_LATENCY_BUCKETS_MS: tuple[float, ...] = (
    5,
    10,
    25,
    50,
    100,
    250,
    500,
    1000,
    2500,
    5000,
    10000,
)


@dataclass(slots=True)
class Histogram:
    buckets: tuple[float, ...] = DEFAULT_LATENCY_BUCKETS_MS
    counts: list[int] = field(default_factory=list)
    total_count: int = 0
    total_sum: float = 0.0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0] * (len(self.buckets) + 1)

    def observe(self, value: float) -> None:
        self.total_count += 1
        self.total_sum += value
        for index, bound in enumerate(self.buckets):
            if value <= bound:
                self.counts[index] += 1
                return
        self.counts[-1] += 1

    def snapshot(self) -> "HistogramSnapshot":
        return HistogramSnapshot(
            buckets=self.buckets,
            counts=tuple(self.counts),
            total_count=self.total_count,
            total_sum=self.total_sum,
        )


@dataclass(frozen=True, slots=True)
class HistogramSnapshot:
    buckets: tuple[float, ...]
    counts: tuple[int, ...]
    total_count: int
    total_sum: float


@dataclass(slots=True)
class AlgorithmMetrics:
    requests_total: int = 0
    requests_failed: int = 0
    inflight: int = 0
    latency_ms: Histogram = field(default_factory=Histogram)
    queue_wait_ms: Histogram = field(default_factory=Histogram)

    def snapshot(self) -> "AlgorithmMetricsSnapshot":
        return AlgorithmMetricsSnapshot(
            requests_total=self.requests_total,
            requests_failed=self.requests_failed,
            inflight=self.inflight,
            latency_ms=self.latency_ms.snapshot(),
            queue_wait_ms=self.queue_wait_ms.snapshot(),
        )


@dataclass(frozen=True, slots=True)
class AlgorithmMetricsSnapshot:
    requests_total: int
    requests_failed: int
    inflight: int
    latency_ms: HistogramSnapshot
    queue_wait_ms: HistogramSnapshot


class InMemoryMetrics:
    """In-memory metrics recorder for algorithm executions."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._metrics: dict[tuple[str, str], AlgorithmMetrics] = {}

    def on_start(self, request: ExecutionRequest[Any, Any]) -> None:
        key = request.spec.key()
        with self._lock:
            metrics = self._metrics.setdefault(key, AlgorithmMetrics())
            metrics.requests_total += 1
            metrics.inflight += 1

    def on_complete(self, request: ExecutionRequest[Any, Any],
                    result: ExecutionResult[Any]) -> None:
        self._record_completion(request, result, failed=False)

    def on_error(self, request: ExecutionRequest[Any, Any],
                 result: ExecutionResult[Any]) -> None:
        self._record_completion(request, result, failed=True)

    def snapshot(self) -> dict[tuple[str, str], AlgorithmMetricsSnapshot]:
        with self._lock:
            return {
                key: metrics.snapshot()
                for key, metrics in self._metrics.items()
            }

    def _record_completion(self, request: ExecutionRequest[Any, Any],
                           result: ExecutionResult[Any],
                           *, failed: bool) -> None:
        key = request.spec.key()
        with self._lock:
            metrics = self._metrics.setdefault(key, AlgorithmMetrics())
            metrics.inflight = max(0, metrics.inflight - 1)
            if failed:
                metrics.requests_failed += 1
            self._observe_timing(metrics, result)

    @staticmethod
    def _observe_timing(metrics: AlgorithmMetrics,
                        result: ExecutionResult[Any]) -> None:
        if result.duration_ms is not None:
            metrics.latency_ms.observe(result.duration_ms)
        if result.queue_wait_ms is not None:
            metrics.queue_wait_ms.observe(result.queue_wait_ms)
