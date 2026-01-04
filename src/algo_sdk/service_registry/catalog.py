"""Helpers for publishing algorithm catalog metadata to the registry."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from algo_sdk.core import AlgorithmSpec, BaseModel, get_registry
from algo_sdk.core.registry import AlgorithmRegistry
from algo_sdk.logging import get_event_logger

from .config import ServiceRegistryConfig, load_config
from .impl.consul_registry import ConsulRegistry
from .errors import ServiceRegistryError
from .protocol import ServiceRegistryProtocol

logger = logging.getLogger(__name__)
_EVENT_LOGGER = get_event_logger()


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
            "algorithm_type": spec.algorithm_type.value,
            "route": route,
            "schema_url": schema_route,
            "absolute_route": f"{base_url}{route}",
            "absolute_schema_url": f"{base_url}{schema_route}",
            "input_schema": spec.input_schema(),
            "output_schema": spec.output_schema(),
        })

    return {
        "service": config.service_name,
        "service_id": config.instance_id,
        "service_version": config.service_version,
        "host": config.service_host,
        "port": config.service_port,
        "base_url": base_url,
        "list_url": f"{base_url}/algorithms",
        "algorithms": items,
    }


def _build_catalog_kv_key(
    config: ServiceRegistryConfig,
    kv_key: str | None,
) -> str:
    if kv_key:
        return kv_key
    return f"algo_services/{config.service_name}/{config.instance_id}/algorithms"


def publish_algorithm_catalog(
    *,
    registry: ServiceRegistryProtocol | None = None,
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
        _EVENT_LOGGER.info(
            "Service registry disabled; skip algorithm catalog publish",
            logger=logger,
        )
        return

    algo_registry = algorithm_registry or get_registry()
    algorithms = tuple(algo_registry.list())
    if registry is None:
        registry = ConsulRegistry(cfg)

    payload = build_algorithm_catalog(cfg, algorithms)
    key = _build_catalog_kv_key(cfg, kv_key)
    registry.set_kv(key, json.dumps(payload))
    _EVENT_LOGGER.info(
        "Published algorithm catalog to registry key=%s",
        key,
        logger=logger,
    )


def _parse_catalog_key(
    key: str,
    kv_prefix: str,
) -> tuple[str, str | None] | None:
    if not key.endswith("/algorithms"):
        return None
    trimmed = key[len(kv_prefix):] if key.startswith(kv_prefix) else key
    parts = [part for part in trimmed.split("/") if part]
    if len(parts) == 2 and parts[1] == "algorithms":
        return parts[0], None
    if len(parts) == 3 and parts[2] == "algorithms":
        return parts[0], parts[1]
    return None


def fetch_registry_algorithm_catalogs(
    *,
    registry: ServiceRegistryProtocol | None = None,
    config: ServiceRegistryConfig | None = None,
    kv_prefix: str = "algo_services/",
    healthy_only: bool = False,
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

    parsed_entries: list[tuple[str, str, str, str | None]] = []
    for key, value in entries.items():
        parsed = _parse_catalog_key(key, kv_prefix)
        if parsed is None:
            continue
        service_name, service_id = parsed
        parsed_entries.append((key, value, service_name, service_id))

    healthy_ids: dict[str, set[str]] = {}
    errors: list[dict[str, str]] = []
    if healthy_only:
        for service_name in {entry[2] for entry in parsed_entries}:
            try:
                instances = registry.get_healthy_service(service_name)
                healthy_ids[service_name] = {
                    instance.service_id for instance in instances
                }
            except ServiceRegistryError as exc:
                errors.append(
                    {
                        "service": service_name,
                        "error": str(exc),
                    }
                )

    catalogs: list[dict[str, object]] = []
    for key, value, service_name, service_id in parsed_entries:
        if healthy_only:
            ids = healthy_ids.get(service_name, set())
            if service_id is None:
                if not ids:
                    continue
            elif service_id not in ids:
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
        if service_id is not None:
            payload.setdefault("service_id", service_id)
        catalogs.append(payload)

    return catalogs, errors
