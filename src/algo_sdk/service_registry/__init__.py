from .config import ServiceRegistryConfig, load_config
from .impl.consul_registry import ConsulRegistry
from .impl.memory_registry import MemoryRegistry
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
    BaseServiceRegistry,
    ServiceRegistryProtocol,
    ServiceStatus,
)

__all__ = [
    # Config
    "ServiceRegistryConfig",
    "load_config",
    # Protocol
    "BaseServiceRegistry",
    "ServiceRegistryProtocol",
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
