"""In-memory service registry implementation for testing."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import override

from .errors import (
    KVOperationError,
    ServiceDeregistrationError,
    ServiceDiscoveryError,
    ServiceRegistrationError,
)
from .protocol import (
    ServiceInstance,
    ServiceRegistration,
    BaseServiceRegistry,
    ServiceStatus,
)


class MemoryRegistry(BaseServiceRegistry):
    """A simple in-memory registry useful for unit tests.

    This class implements the BaseServiceRegistry abstract base class using an
    in-memory storage backend. Ideal for testing scenarios where a real
    Consul instance is not available.
    """

    _services: dict[str, dict[str, ServiceInstance]]
    _kv_store: dict[str, str]
    _healthy: bool
    _lock: threading.RLock

    def __init__(self, *, healthy: bool = True) -> None:
        self._services = defaultdict(dict)
        self._kv_store = {}
        self._healthy = healthy
        self._lock = threading.RLock()

    @override
    def register(self, registration: ServiceRegistration) -> None:
        """Register a service instance in memory."""
        instance = ServiceInstance(
            service_id=registration.service_id,
            service_name=registration.service_name,
            host=registration.host,
            port=registration.port,
            tags=registration.tags,
            meta=registration.meta,
            status=ServiceStatus.PASSING,
        )
        with self._lock:
            service_map = self._services[registration.service_name]
            if registration.service_id in service_map:
                raise ServiceRegistrationError(
                    f"Service already registered: {registration.service_id}")
            service_map[registration.service_id] = instance

    @override
    def deregister(self, service_id: str) -> None:
        """Deregister a service instance by ID."""
        with self._lock:
            for name, service_map in self._services.items():
                if service_id in service_map:
                    del service_map[service_id]
                    if not service_map:
                        del self._services[name]
                    return
        raise ServiceDeregistrationError(f"Service not found: {service_id}")

    @override
    def get_service(self, service_name: str) -> list[ServiceInstance]:
        """Return all registered instances for a service name."""
        with self._lock:
            service_map = self._services.get(service_name, {})
            return [service_map[key] for key in sorted(service_map)]

    @override
    def get_healthy_service(self, service_name: str) -> list[ServiceInstance]:
        """Return healthy instances (status PASSING) for a service name."""
        try:
            return [
                instance for instance in self.get_service(service_name)
                if instance.status == ServiceStatus.PASSING
            ]
        except Exception as exc:  # pragma: no cover - defensive wrap
            raise ServiceDiscoveryError(
                f"Failed to query healthy service: {service_name}") from exc

    @override
    def set_kv(self, key: str, value: str) -> None:
        """Set a key-value entry."""
        with self._lock:
            self._kv_store[key] = value

    @override
    def get_kv(self, key: str) -> str | None:
        """Get a value by key."""
        with self._lock:
            return self._kv_store.get(key)

    @override
    def delete_kv(self, key: str) -> None:
        """Delete a key-value entry."""
        with self._lock:
            if key not in self._kv_store:
                raise KVOperationError(f"KV key not found: {key}")
            del self._kv_store[key]

    @override
    def is_healthy(self) -> bool:
        """Return the configured health status."""
        return self._healthy

    def set_health(self, healthy: bool) -> None:
        """Toggle registry health for testing."""
        with self._lock:
            self._healthy = healthy
