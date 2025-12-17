"""Service registry configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


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
    return ServiceRegistryConfig()
