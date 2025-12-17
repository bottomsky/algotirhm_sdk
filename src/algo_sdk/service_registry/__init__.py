"""Service registry module for algorithm service discovery.

This module provides a unified interface for service registration and
discovery, with Consul as the default implementation.

Example:
    >>> from algo_sdk.service_registry import (
    ...     ConsulRegistry,
    ...     ServiceRegistration,
    ...     HealthCheck,
    ...     load_config,
    ... )
    >>>
    >>> # Load configuration from environment
    >>> config = load_config()
    >>>
    >>> # Create registry
    >>> registry = ConsulRegistry(config)
    >>>
    >>> # Register a service
    >>> registration = ServiceRegistration(
    ...     service_name="algo-core-service",
    ...     service_id="algo-core-service-1",
    ...     host="192.168.1.10",
    ...     port=8000,
    ...     tags=("v1", "algorithm"),
    ...     health_check=HealthCheck(
    ...         http_endpoint="/healthz",
    ...         interval_seconds=10,
    ...         timeout_seconds=5,
    ...     ),
    ... )
    >>> registry.register(registration)
    >>>
    >>> # Discover services
    >>> instances = registry.get_healthy_service("algo-core-service")
"""

from .config import ServiceRegistryConfig, load_config
from .consul_registry import ConsulRegistry
from .memory_registry import MemoryRegistry
from .errors import (
    KVOperationError,
    ServiceDeregistrationError,
    ServiceDiscoveryError,
    ServiceRegistrationError,
    ServiceRegistryConnectionError,
    ServiceRegistryError,
)
from .protocol import (
    HealthCheck,
    ServiceInstance,
    ServiceRegistration,
    ServiceRegistry,
    ServiceStatus,
)

__all__ = [
    # Config
    "ServiceRegistryConfig",
    "load_config",
    # Protocol
    "ServiceRegistry",
    "ServiceInstance",
    "ServiceRegistration",
    "HealthCheck",
    "ServiceStatus",
    # Implementation
    "ConsulRegistry",
    "MemoryRegistry",
    # Errors
    "ServiceRegistryError",
    "ServiceRegistrationError",
    "ServiceDeregistrationError",
    "ServiceDiscoveryError",
    "ServiceRegistryConnectionError",
    "KVOperationError",
]
