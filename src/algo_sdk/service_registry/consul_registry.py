"""Consul service registry implementation."""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from http.client import HTTPResponse
from typing import ClassVar, cast, override

from .config import ServiceRegistryConfig, load_config
from .errors import (
    KVOperationError,
    ServiceDeregistrationError,
    ServiceDiscoveryError,
    ServiceRegistrationError,
    ServiceRegistryConnectionError,
)
from .protocol import (
    HealthCheck,
    ServiceInstance,
    ServiceRegistration,
    BaseServiceRegistry,
    ServiceStatus,
)

logger = logging.getLogger(__name__)


def _to_str(value: object) -> str:
    """Convert value to string safely."""
    if value is None:
        return ""
    return str(value)


def _to_int(value: object, default: int = 0) -> int:
    """Convert value to int safely."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return default


def _to_str_tuple(value: object) -> tuple[str, ...]:
    """Convert value to tuple of strings."""
    items: Iterable[object]
    if isinstance(value, tuple):
        items = cast(Iterable[object], value)
    elif isinstance(value, list):
        items = cast(Iterable[object], value)
    elif isinstance(value, Iterable):
        items = value
    else:
        return ()
    return tuple(_to_str(v) for v in items)


def _to_str_dict(value: object) -> dict[str, str]:
    """Convert value to dict of strings."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {_to_str(k): _to_str(v) for k, v in mapping.items()}
    return {}


def _as_object_dict(value: object) -> dict[str, object]:
    """Ensure the value is a dict[str, object] or return empty."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(k): v for k, v in mapping.items()}
    return {}


def _coerce_dict_list(result: object) -> list[dict[str, object]]:
    """Convert JSON result to a list of object dictionaries."""
    if isinstance(result, list):
        dicts: list[dict[str, object]] = []
        for item in cast(list[object], result):
            mapped = _as_object_dict(item)
            if mapped:
                dicts.append(mapped)
        return dicts
    if isinstance(result, Mapping):
        mapped = _as_object_dict(cast(Mapping[object, object], result))
        return [mapped] if mapped else []
    return []


class ConsulRegistry(BaseServiceRegistry):
    """Consul-based service registry implementation.

    This class implements the BaseServiceRegistry abstract base class using
    Consul as the backend. It provides service registration, discovery, and
    key-value storage capabilities.

    Example:
        >>> config = ServiceRegistryConfig(host="http://localhost:8500")
        >>> registry = ConsulRegistry(config)
        >>> registration = ServiceRegistration(
        ...     service_name="my-service",
        ...     service_id="my-service-1",
        ...     host="192.168.1.10",
        ...     port=8080,
        ... )
        >>> registry.register(registration)
    """

    DEFAULT_TIMEOUT: ClassVar[int] = 10

    _config: ServiceRegistryConfig
    _base_url: str
    _timeout: int

    def __init__(
        self,
        config: ServiceRegistryConfig | None = None,
    ) -> None:
        """Initialize Consul registry.

        Args:
            config: Registry configuration. If None, loads from environment.
        """
        self._config = config or load_config()
        self._base_url = self._config.host.rstrip("/")
        self._timeout = self.DEFAULT_TIMEOUT

    @property
    def config(self) -> ServiceRegistryConfig:
        """Get the registry configuration."""
        return self._config

    @override
    def register(self, registration: ServiceRegistration) -> None:
        """Register a service instance with Consul.

        Args:
            registration: Service registration details

        Raises:
            ServiceRegistrationError: If registration fails
        """
        url = f"{self._base_url}/v1/agent/service/register"
        payload = self._build_registration_payload(registration)

        try:
            self._http_put(url, payload)
            logger.info(
                "Registered service: %s (id=%s)",
                registration.service_name,
                registration.service_id,
            )
        except Exception as e:
            msg = f"Failed to register service: {registration.service_id}"
            logger.exception(msg)
            raise ServiceRegistrationError(msg) from e

    @override
    def deregister(self, service_id: str) -> None:
        """Deregister a service instance from Consul.

        Args:
            service_id: The service instance ID to deregister

        Raises:
            ServiceDeregistrationError: If deregistration fails
        """
        url = f"{self._base_url}/v1/agent/service/deregister/{service_id}"

        try:
            self._http_put(url, None)
            logger.info("Deregistered service: %s", service_id)
        except Exception as e:
            msg = f"Failed to deregister service: {service_id}"
            logger.exception(msg)
            raise ServiceDeregistrationError(msg) from e

    @override
    def get_service(self, service_name: str) -> list[ServiceInstance]:
        """Get all instances of a service.

        Args:
            service_name: The service name to query

        Returns:
            List of service instances

        Raises:
            ServiceDiscoveryError: If query fails
        """
        url = f"{self._base_url}/v1/catalog/service/{service_name}"

        try:
            data = self._http_get(url)
            return self._parse_service_instances(data)
        except Exception as e:
            msg = f"Failed to get service: {service_name}"
            logger.exception(msg)
            raise ServiceDiscoveryError(msg) from e

    @override
    def get_healthy_service(self, service_name: str) -> list[ServiceInstance]:
        """Get all healthy instances of a service.

        Args:
            service_name: The service name to query

        Returns:
            List of healthy service instances

        Raises:
            ServiceDiscoveryError: If query fails
        """
        url = f"{self._base_url}/v1/health/service/{service_name}?passing=true"

        try:
            data = self._http_get(url)
            return self._parse_health_service_instances(data)
        except Exception as e:
            msg = f"Failed to get healthy service: {service_name}"
            logger.exception(msg)
            raise ServiceDiscoveryError(msg) from e

    @override
    def set_kv(self, key: str, value: str) -> None:
        """Set a key-value pair in Consul KV store.

        Args:
            key: The key
            value: The value

        Raises:
            KVOperationError: If operation fails
        """
        url = f"{self._base_url}/v1/kv/{key}"

        try:
            self._http_put(url, value.encode("utf-8"), is_raw=True)
            logger.debug("Set KV: %s", key)
        except Exception as e:
            msg = f"Failed to set KV: {key}"
            logger.exception(msg)
            raise KVOperationError(msg) from e

    @override
    def get_kv(self, key: str) -> str | None:
        """Get a value by key from Consul KV store.

        Args:
            key: The key to query

        Returns:
            The value if found, None otherwise

        Raises:
            KVOperationError: If query fails
        """
        url = f"{self._base_url}/v1/kv/{key}"

        try:
            data = self._http_get(url)
            if not data:
                return None
            # Consul returns base64 encoded value
            encoded_value = data[0].get("Value")
            if isinstance(encoded_value, str):
                raw = base64.b64decode(encoded_value.encode("utf-8"))
            elif isinstance(encoded_value, (bytes, bytearray)):
                raw = base64.b64decode(encoded_value)
            else:
                return None
            return raw.decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            msg = f"Failed to get KV: {key}"
            logger.exception(msg)
            raise KVOperationError(msg) from e
        except Exception as e:
            msg = f"Failed to get KV: {key}"
            logger.exception(msg)
            raise KVOperationError(msg) from e

    @override
    def list_kv_prefix(self, prefix: str) -> dict[str, str]:
        """List key-value entries under a prefix from Consul KV store."""
        url = f"{self._base_url}/v1/kv/{prefix}?recurse=true"
        entries: dict[str, str] = {}

        try:
            data = self._http_get(url)
            if not data:
                return {}
            for item in data:
                key = item.get("Key")
                if not isinstance(key, str):
                    continue
                encoded_value = item.get("Value")
                if isinstance(encoded_value, str):
                    raw = base64.b64decode(encoded_value.encode("utf-8"))
                elif isinstance(encoded_value, (bytes, bytearray)):
                    raw = base64.b64decode(encoded_value)
                else:
                    continue
                entries[key] = raw.decode("utf-8")
            return entries
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            msg = f"Failed to list KV prefix: {prefix}"
            logger.exception(msg)
            raise KVOperationError(msg) from e
        except Exception as e:
            msg = f"Failed to list KV prefix: {prefix}"
            logger.exception(msg)
            raise KVOperationError(msg) from e

    @override
    def delete_kv(self, key: str) -> None:
        """Delete a key-value pair from Consul KV store.

        Args:
            key: The key to delete

        Raises:
            KVOperationError: If operation fails
        """
        url = f"{self._base_url}/v1/kv/{key}"

        try:
            self._http_delete(url)
            logger.debug("Deleted KV: %s", key)
        except Exception as e:
            msg = f"Failed to delete KV: {key}"
            logger.exception(msg)
            raise KVOperationError(msg) from e

    @override
    def is_healthy(self) -> bool:
        """Check if the Consul connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        url = f"{self._base_url}/v1/status/leader"

        try:
            leader = self._http_get(url)
            return bool(leader)
        except Exception:
            logger.warning("Consul health check failed")
            return False

    def _build_registration_payload(
        self,
        registration: ServiceRegistration,
    ) -> dict[str, object]:
        """Build Consul registration payload."""
        payload: dict[str, object] = {
            "ID": registration.service_id,
            "Name": registration.service_name,
            "Address": registration.host,
            "Port": registration.port,
        }

        if registration.tags:
            payload["Tags"] = list(registration.tags)

        if registration.meta:
            payload["Meta"] = registration.meta

        if registration.health_check:
            payload["Check"] = self._build_check_payload(
                registration.health_check,
                registration.host,
                registration.port,
            )

        return payload

    def _build_check_payload(
        self,
        health_check: HealthCheck,
        host: str,
        port: int,
    ) -> dict[str, object]:
        """Build Consul health check payload."""
        check: dict[str, object] = {
            "Interval": f"{health_check.interval_seconds}s",
            "Timeout": f"{health_check.timeout_seconds}s",
        }

        if health_check.http_endpoint:
            endpoint = health_check.http_endpoint
            if not endpoint.startswith("http"):
                endpoint = f"http://{host}:{port}{endpoint}"
            check["HTTP"] = endpoint

        if health_check.deregister_after_seconds:
            check["DeregisterCriticalServiceAfter"] = (
                f"{health_check.deregister_after_seconds}s")

        return check

    def _parse_service_instances(
        self,
        data: list[dict[str, object]],
    ) -> list[ServiceInstance]:
        """Parse Consul catalog service response."""
        instances: list[ServiceInstance] = []
        for item in data:
            service_address = item.get("ServiceAddress")
            address = item.get("Address", "")
            host = _to_str(service_address if service_address else address)
            instance = ServiceInstance(
                service_id=_to_str(item.get("ServiceID", "")),
                service_name=_to_str(item.get("ServiceName", "")),
                host=host,
                port=_to_int(item.get("ServicePort", 0)),
                tags=_to_str_tuple(item.get("ServiceTags")),
                meta=_to_str_dict(item.get("ServiceMeta")),
                status=ServiceStatus.UNKNOWN,
            )
            instances.append(instance)
        return instances

    def _parse_health_service_instances(
        self,
        data: list[dict[str, object]],
    ) -> list[ServiceInstance]:
        """Parse Consul health service response."""
        instances: list[ServiceInstance] = []
        for item in data:
            service = _as_object_dict(item.get("Service", {}))
            if not service:
                continue
            instance = ServiceInstance(
                service_id=_to_str(service.get("ID", "")),
                service_name=_to_str(service.get("Service", "")),
                host=_to_str(service.get("Address", "")),
                port=_to_int(service.get("Port", 0)),
                tags=_to_str_tuple(service.get("Tags")),
                meta=_to_str_dict(service.get("Meta")),
                status=ServiceStatus.PASSING,
            )
            instances.append(instance)
        return instances

    def _http_get(self, url: str) -> list[dict[str, object]]:
        """Perform HTTP GET request."""
        request = urllib.request.Request(url, method="GET")
        request.add_header("Accept", "application/json")

        try:
            with cast(
                    HTTPResponse,
                    urllib.request.urlopen(request, timeout=self._timeout),
            ) as response:
                content_bytes = response.read()
                if not content_bytes:
                    return []
                content = content_bytes.decode("utf-8")
                result = cast(object, json.loads(content))
                return _coerce_dict_list(result)
        except urllib.error.URLError as e:
            raise ServiceRegistryConnectionError(
                f"Failed to connect to Consul: {e}") from e

    def _http_put(
        self,
        url: str,
        data: dict[str, object] | bytes | None,
        *,
        is_raw: bool = False,
    ) -> None:
        """Perform HTTP PUT request."""
        if data is None:
            body = None
        elif is_raw and isinstance(data, bytes):
            body = data
        else:
            body = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(url, data=body, method="PUT")
        request.add_header("Content-Type", "application/json")

        try:
            with cast(
                    HTTPResponse,
                    urllib.request.urlopen(request, timeout=self._timeout),
            ) as response:
                _ = response.read()  # Consume response
        except urllib.error.URLError as e:
            raise ServiceRegistryConnectionError(
                f"Failed to connect to Consul: {e}") from e

    def _http_delete(self, url: str) -> None:
        """Perform HTTP DELETE request."""
        request = urllib.request.Request(url, method="DELETE")

        try:
            with cast(
                    HTTPResponse,
                    urllib.request.urlopen(request, timeout=self._timeout),
            ) as response:
                _ = response.read()  # Consume response
        except urllib.error.URLError as e:
            raise ServiceRegistryConnectionError(
                f"Failed to connect to Consul: {e}") from e
