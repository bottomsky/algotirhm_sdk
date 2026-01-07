"""Public API entry point for algo_sdk.

Use this module for supported imports. Subpackages are internal.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from algo_decorators import Algorithm, DefaultAlgorithmDecorator

from .core import (
    AlgorithmError,
    AlgorithmLifecycleProtocol,
    AlgorithmMarker,
    AlgorithmNotFoundError,
    AlgorithmRegistrationError,
    AlgorithmRegistry,
    AlgorithmSpec,
    AlgorithmType,
    AlgorithmValidationError,
    AlreadyInStateError,
    ApplicationFactoryProtocol,
    BaseAlgorithm,
    BaseModel,
    DispatchingExecutor,
    ExecutionConfig,
    ExecutionError,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutorProtocol,
    HyperParams,
    InProcessExecutor,
    InvalidTransitionError,
    IsolatedProcessPoolExecutor,
    LoggingConfig,
    ProcessPoolExecutor,
    ServiceLifecycleContext,
    ServiceLifecycleError,
    ServiceLifecycleHookProtocol,
    ServiceLifecyclePhase,
    ServiceLifecycleProtocol,
    ServiceState,
    get_registry,
)
from .http import AlgorithmHttpService, ObservationHooks, create_app, run
from .http.impl import server as http_server
from .observability import (
    InMemoryMetrics,
    InMemoryTracer,
    create_observation_hooks,
)
from .protocol import (
    AlgorithmContext,
    AlgorithmRequest,
    AlgorithmResponse,
    api_error,
    api_success,
)
from .runtime import (
    ResponseMeta,
    build_service_runtime,
    execution_context,
    get_current_context,
    get_current_request_datetime,
    get_current_request_id,
    get_current_trace_id,
    get_response_meta,
    set_response_code,
    set_response_context,
    set_response_message,
)
from .runtime.impl.service_runtime import ServiceRuntime
from .service_registry import (
    ConsulRegistry,
    HealthCheck,
    MemoryRegistry,
    ServiceRegistration,
    ServiceRegistryConfig,
    ServiceRegistryProtocol,
    ServiceStatus,
    load_config,
)
from .service_registry.catalog import fetch_registry_algorithm_catalogs


def __getattr__(name: str) -> Any:
    if name in {"Algorithm", "DefaultAlgorithmDecorator"}:
        module = import_module("algo_decorators")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Algorithm",
    "DefaultAlgorithmDecorator",
    "BaseModel",
    "AlgorithmContext",
    "AlgorithmRequest",
    "AlgorithmResponse",
    "api_success",
    "api_error",
    "AlgorithmError",
    "AlgorithmMarker",
    "AlgorithmNotFoundError",
    "AlgorithmRegistrationError",
    "AlgorithmValidationError",
    "AlgorithmLifecycleProtocol",
    "BaseAlgorithm",
    "AlgorithmSpec",
    "AlgorithmType",
    "ExecutionConfig",
    "ExecutionMode",
    "LoggingConfig",
    "HyperParams",
    "AlgorithmRegistry",
    "get_registry",
    "ApplicationFactoryProtocol",
    "ExecutionError",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutorProtocol",
    "InProcessExecutor",
    "ProcessPoolExecutor",
    "IsolatedProcessPoolExecutor",
    "DispatchingExecutor",
    "AlgorithmHttpService",
    "ObservationHooks",
    "create_app",
    "run",
    "http_server",
    "InMemoryMetrics",
    "InMemoryTracer",
    "create_observation_hooks",
    "build_service_runtime",
    "execution_context",
    "get_current_context",
    "get_current_request_id",
    "get_current_trace_id",
    "get_current_request_datetime",
    "set_response_code",
    "set_response_message",
    "set_response_context",
    "get_response_meta",
    "ResponseMeta",
    "ServiceRuntime",
    "ServiceState",
    "ServiceLifecyclePhase",
    "ServiceLifecycleContext",
    "ServiceLifecycleError",
    "AlreadyInStateError",
    "InvalidTransitionError",
    "ServiceLifecycleHookProtocol",
    "ServiceLifecycleProtocol",
    "ConsulRegistry",
    "MemoryRegistry",
    "ServiceRegistryProtocol",
    "ServiceRegistryConfig",
    "ServiceRegistration",
    "HealthCheck",
    "ServiceStatus",
    "load_config",
    "fetch_registry_algorithm_catalogs",
]
