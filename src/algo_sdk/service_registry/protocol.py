"""Service registry protocol definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class ServiceStatus(Enum):
    """Service health status."""

    PASSING = "passing"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ServiceInstance:
    """Represents a registered service instance."""

    service_id: str
    service_name: str
    host: str
    port: int
    tags: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, str] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.UNKNOWN


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """Health check configuration."""

    # HTTP health check endpoint
    http_endpoint: str | None = None

    # Check interval in seconds
    interval_seconds: int = 10

    # Timeout in seconds
    timeout_seconds: int = 5

    # Deregister critical service after this duration (seconds)
    deregister_after_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class ServiceRegistration:
    """Service registration request."""

    service_name: str
    service_id: str
    host: str
    port: int
    tags: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, str] = field(default_factory=dict)
    health_check: HealthCheck | None = None


class ServiceRegistry(Protocol):
    """Protocol for service registry implementations.

    This protocol defines the interface for service discovery and registration.
    Implementations can use Consul, etcd, Kubernetes, or other backends.
    """

    def register(self, registration: ServiceRegistration) -> None:
        """Register a service instance.

        Args:
            registration: Service registration details

        Raises:
            ServiceRegistryError: If registration fails
        """
        ...

    def deregister(self, service_id: str) -> None:
        """Deregister a service instance.

        Args:
            service_id: The service instance ID to deregister

        Raises:
            ServiceRegistryError: If deregistration fails
        """
        ...

    def get_service(self, service_name: str) -> list[ServiceInstance]:
        """Get all instances of a service.

        Args:
            service_name: The service name to query

        Returns:
            List of service instances

        Raises:
            ServiceRegistryError: If query fails
        """
        ...

    def get_healthy_service(self, service_name: str) -> list[ServiceInstance]:
        """Get all healthy instances of a service.

        Args:
            service_name: The service name to query

        Returns:
            List of healthy service instances

        Raises:
            ServiceRegistryError: If query fails
        """
        ...

    def set_kv(self, key: str, value: str) -> None:
        """Set a key-value pair in the registry.

        Args:
            key: The key
            value: The value

        Raises:
            ServiceRegistryError: If operation fails
        """
        ...

    def get_kv(self, key: str) -> str | None:
        """Get a value by key from the registry.

        Args:
            key: The key to query

        Returns:
            The value if found, None otherwise

        Raises:
            ServiceRegistryError: If query fails
        """
        ...

    def delete_kv(self, key: str) -> None:
        """Delete a key-value pair from the registry.

        Args:
            key: The key to delete

        Raises:
            ServiceRegistryError: If operation fails
        """
        ...

    def is_healthy(self) -> bool:
        """Check if the registry connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        ...
