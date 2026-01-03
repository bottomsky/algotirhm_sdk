"""Service registry configuration."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field, replace


def _get_env(key: str, default: str) -> str:
    """Get environment variable with default value."""
    return os.getenv(key, default)


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


_INSTANCE_ID: str | None = os.getenv("SERVICE_INSTANCE_ID")


def _build_instance_id(service_name: str) -> str:
    global _INSTANCE_ID
    if _INSTANCE_ID:
        return _INSTANCE_ID
    suffix = uuid.uuid4().hex[:8]
    _INSTANCE_ID = f"{service_name}-{suffix}"
    return _INSTANCE_ID


@dataclass(frozen=True, slots=True)
class ServiceRegistryConfig:
    """Configuration for service registry."""

    # Registry host address
    host: str = field(
        default_factory=lambda: _get_env(
            "SERVICE_REGISTRY_HOST", "http://127.0.0.1:8500"
        )
    )

    # Whether service registration is enabled
    enabled: bool = field(
        default_factory=lambda: _get_env_bool(
            "SERVICE_REGISTRY_ENABLED", False
        )
    )

    # Service name
    service_name: str = field(
        default_factory=lambda: _get_env("SERVICE_NAME", "algo-core-service")
    )

    # Service version
    service_version: str = field(
        default_factory=lambda: _get_env("SERVICE_VERSION", "unknown")
    )

    # Service instance ID (auto-generated if not provided)
    instance_id: str | None = field(
        default_factory=lambda: os.getenv("SERVICE_INSTANCE_ID")
    )

    # Service host for health check
    service_host: str = field(
        default_factory=lambda: _get_env("SERVICE_HOST", "127.0.0.1")
    )

    # Service port
    service_port: int = field(
        default_factory=lambda: _get_env_int("SERVICE_PORT", 8000)
    )

    # Health check interval in seconds
    health_check_interval: int = field(
        default_factory=lambda: _get_env_int("HEALTH_CHECK_INTERVAL", 10)
    )

    # Health check timeout in seconds
    health_check_timeout: int = field(
        default_factory=lambda: _get_env_int("HEALTH_CHECK_TIMEOUT", 5)
    )


def load_config() -> ServiceRegistryConfig:
    """Load service registry configuration from environment."""
    config = ServiceRegistryConfig()
    instance_id = config.instance_id
    if instance_id is None or not instance_id.strip():
        instance_id = _build_instance_id(config.service_name)
        return replace(config, instance_id=instance_id)
    return config
