"""Helpers for publishing algorithm catalog metadata to the registry."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from algo_sdk.core import AlgorithmSpec, BaseModel, get_registry
from algo_sdk.core.registry import AlgorithmRegistry

from .config import ServiceRegistryConfig, load_config
from .consul_registry import ConsulRegistry
from .errors import ServiceRegistryError
from .protocol import BaseServiceRegistry

logger = logging.getLogger(__name__)


def _build_base_url(config: ServiceRegistryConfig) -> str:
    """Build base URL for the current service."""
    return f"http://{config.service_host}:{config.service_port}"


def build_algorithm_catalog(
    config: ServiceRegistryConfig,
    algorithms: Iterable[AlgorithmSpec[BaseModel, BaseModel]],
) -> dict[str, object]:
    """Construct catalog payload for registered algorithms."""
    base_url = _build_base_url(config)
    items: list[dict[str, object]] = []

    for spec in algorithms:
        route = f"/algorithms/{spec.name}/{spec.version}"
        schema_route = f"{route}/schema"
        items.append({
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "route": route,
            "schema_url": schema_route,
            "absolute_route": f"{base_url}{route}",
            "absolute_schema_url": f"{base_url}{schema_route}",
            "input_schema": spec.input_schema(),
            "output_schema": spec.output_schema(),
        })

    return {
        "service": config.service_name,
        "base_url": base_url,
        "list_url": f"{base_url}/algorithms",
        "algorithms": items,
    }


def publish_algorithm_catalog(
    *,
    registry: BaseServiceRegistry | None = None,
    config: ServiceRegistryConfig | None = None,
    algorithm_registry: AlgorithmRegistry | None = None,
    kv_key: str | None = None,
) -> None:
    """Publish registered algorithms to service registry KV.

    This function collects all algorithms registered via the Algorithm
    decorator, builds a catalog containing their routes and JSON schemas,
    and writes it to the configured registry backend.
    """
    cfg = config or load_config()
    if not cfg.enabled:
        logger.info(
            "Service registry disabled; skip algorithm catalog publish", )
        return

    algo_registry = algorithm_registry or get_registry()
    algorithms = tuple(algo_registry.list())
    if registry is None:
        registry = ConsulRegistry(cfg)

    payload = build_algorithm_catalog(cfg, algorithms)
    key = kv_key or f"services/{cfg.service_name}/algorithms"
    registry.set_kv(key, json.dumps(payload))
    logger.info("Published algorithm catalog to registry key=%s", key)


def fetch_registry_algorithm_catalogs(
    *,
    registry: BaseServiceRegistry | None = None,
    config: ServiceRegistryConfig | None = None,
    kv_prefix: str = "services/",
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Fetch algorithm catalogs from the registry KV prefix."""
    cfg = config or load_config()
    if registry is None:
        registry = ConsulRegistry(cfg)

    try:
        entries = registry.list_kv_prefix(kv_prefix)
    except ServiceRegistryError:
        raise
    except Exception as exc:
        raise ServiceRegistryError(str(exc)) from exc

    catalogs: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for key, value in entries.items():
        if not key.endswith("/algorithms"):
            continue
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            errors.append({"key": key, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            errors.append(
                {"key": key, "error": "catalog payload is not a dict"}
                )
            continue
        payload.setdefault("kv_key", key)
        catalogs.append(payload)

    return catalogs, errors
