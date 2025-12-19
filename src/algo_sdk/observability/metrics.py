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

    def render_prometheus_text(self, *, namespace: str = "algo_sdk") -> str:
        return render_prometheus_text(self.snapshot(), namespace=namespace)

    def build_otel_metrics(self, *,
                           service_name: str = "algo-sdk") -> dict[str, Any]:
        return build_otel_metrics(self.snapshot(), service_name=service_name)

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


def render_prometheus_text(
    snapshot: dict[tuple[str, str], AlgorithmMetricsSnapshot],
    *,
    namespace: str = "algo_sdk",
) -> str:
    lines: list[str] = []
    prefix = namespace.strip("_")
    if prefix:
        prefix = f"{prefix}_"

    lines.extend([
        f"# HELP {prefix}requests_total Total algorithm requests.",
        f"# TYPE {prefix}requests_total counter",
        f"# HELP {prefix}requests_failed_total Total failed algorithm requests.",
        f"# TYPE {prefix}requests_failed_total counter",
        f"# HELP {prefix}requests_inflight Current inflight algorithm requests.",
        f"# TYPE {prefix}requests_inflight gauge",
        f"# HELP {prefix}request_latency_ms Algorithm execution latency in ms.",
        f"# TYPE {prefix}request_latency_ms histogram",
        f"# HELP {prefix}queue_wait_ms Queue wait time in ms.",
        f"# TYPE {prefix}queue_wait_ms histogram",
    ])

    for (algo_name, algo_version), metrics in snapshot.items():
        labels = {
            "algo_name": algo_name,
            "algo_version": algo_version,
        }
        lines.append(
            f"{prefix}requests_total{_format_labels(labels)} "
            f"{metrics.requests_total}"
        )
        lines.append(
            f"{prefix}requests_failed_total{_format_labels(labels)} "
            f"{metrics.requests_failed}"
        )
        lines.append(
            f"{prefix}requests_inflight{_format_labels(labels)} "
            f"{metrics.inflight}"
        )

        _append_histogram(
            lines,
            f"{prefix}request_latency_ms",
            metrics.latency_ms,
            labels,
        )
        _append_histogram(
            lines,
            f"{prefix}queue_wait_ms",
            metrics.queue_wait_ms,
            labels,
        )

    return "\n".join(lines) + "\n"


def build_otel_metrics(
    snapshot: dict[tuple[str, str], AlgorithmMetricsSnapshot],
    *,
    service_name: str = "algo-sdk",
) -> dict[str, Any]:
    metrics_payload: list[dict[str, Any]] = []
    for (algo_name, algo_version), metrics in snapshot.items():
        attributes = [
            {"key": "algo.name", "value": {"stringValue": algo_name}},
            {"key": "algo.version", "value": {"stringValue": algo_version}},
        ]
        metrics_payload.extend([
            _otel_sum_metric(
                "requests_total",
                "Total algorithm requests.",
                metrics.requests_total,
                attributes,
            ),
            _otel_sum_metric(
                "requests_failed_total",
                "Total failed algorithm requests.",
                metrics.requests_failed,
                attributes,
            ),
            _otel_gauge_metric(
                "requests_inflight",
                "Current inflight algorithm requests.",
                metrics.inflight,
                attributes,
            ),
            _otel_histogram_metric(
                "request_latency_ms",
                "Algorithm execution latency in ms.",
                metrics.latency_ms,
                attributes,
            ),
            _otel_histogram_metric(
                "queue_wait_ms",
                "Queue wait time in ms.",
                metrics.queue_wait_ms,
                attributes,
            ),
        ])

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": service_name},
                        },
                    ],
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "algo_sdk.observability"},
                        "metrics": metrics_payload,
                    }
                ],
            }
        ]
    }


def _append_histogram(
    lines: list[str],
    metric_name: str,
    snapshot: HistogramSnapshot,
    labels: dict[str, str],
) -> None:
    cumulative = 0
    for bound, count in zip(snapshot.buckets, snapshot.counts[:-1]):
        cumulative += count
        bound_labels = dict(labels)
        bound_labels["le"] = _format_float(bound)
        lines.append(
            f"{metric_name}_bucket{_format_labels(bound_labels)} "
            f"{cumulative}"
        )

    cumulative += snapshot.counts[-1]
    inf_labels = dict(labels)
    inf_labels["le"] = "+Inf"
    lines.append(
        f"{metric_name}_bucket{_format_labels(inf_labels)} "
        f"{cumulative}"
    )
    lines.append(
        f"{metric_name}_sum{_format_labels(labels)} "
        f"{_format_float(snapshot.total_sum)}"
    )
    lines.append(
        f"{metric_name}_count{_format_labels(labels)} "
        f"{snapshot.total_count}"
    )


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{key}="{_escape_label(value)}"'
             for key, value in labels.items()]
    return "{" + ",".join(parts) + "}"


def _escape_label(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("\n", "\\n")
    return escaped.replace("\"", "\\\"")


def _format_float(value: float) -> str:
    return format(value, "g")


def _otel_sum_metric(
    name: str,
    description: str,
    value: int,
    attributes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": "1",
        "sum": {
            "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
            "isMonotonic": True,
            "dataPoints": [
                {
                    "attributes": attributes,
                    "asInt": value,
                }
            ],
        },
    }


def _otel_gauge_metric(
    name: str,
    description: str,
    value: int,
    attributes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": "1",
        "gauge": {
            "dataPoints": [
                {
                    "attributes": attributes,
                    "asInt": value,
                }
            ],
        },
    }


def _otel_histogram_metric(
    name: str,
    description: str,
    snapshot: HistogramSnapshot,
    attributes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": "ms",
        "histogram": {
            "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
            "dataPoints": [
                {
                    "attributes": attributes,
                    "count": snapshot.total_count,
                    "sum": snapshot.total_sum,
                    "explicitBounds": list(snapshot.buckets),
                    "bucketCounts": list(snapshot.counts),
                }
            ],
        },
    }
