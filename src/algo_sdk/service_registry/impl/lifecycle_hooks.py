from __future__ import annotations

import logging

from algo_sdk.core.registry import AlgorithmRegistry, get_registry
from algo_sdk.logging import get_event_logger
from algo_sdk.runtime import (
    ServiceLifecycleContext,
    ServiceLifecycleHookProtocol,
    ServiceLifecyclePhase,
)

from ..catalog import _build_catalog_kv_key, publish_algorithm_catalog
from ..config import ServiceRegistryConfig, load_config
from ..impl.consul_registry import ConsulRegistry
from ..protocol import (
    HealthCheck,
    ServiceRegistration,
    ServiceRegistryProtocol,
)

_LOGGER = logging.getLogger(__name__)
_EVENT_LOGGER = get_event_logger()


class ServiceRegistryHook(ServiceLifecycleHookProtocol):
    """Register service + publish algorithm catalog during lifecycle."""

    priority = 0

    def __init__(
        self,
        *,
        registry: ServiceRegistryProtocol | None = None,
        config: ServiceRegistryConfig | None = None,
        algorithm_registry: AlgorithmRegistry | None = None,
        kv_key: str | None = None,
        health_check_endpoint: str | None = "/healthz",
        priority: int | None = None,
    ) -> None:
        self._config = config or load_config()
        self._registry = registry
        self._algorithm_registry = algorithm_registry or get_registry()
        self._kv_key = kv_key
        self._health_check_endpoint = health_check_endpoint
        self._service_id = self._build_service_id(self._config)
        self._registered = False
        if priority is not None:
            self.priority = priority

    def can_handle(self, phase: ServiceLifecyclePhase) -> bool:
        return phase in {
            ServiceLifecyclePhase.RUNNING,
            ServiceLifecyclePhase.SHUTDOWN,
        }

    def before(self, ctx: ServiceLifecycleContext) -> None:
        if not self._config.enabled:
            return
        if ctx.phase is ServiceLifecyclePhase.RUNNING:
            self._register_if_needed()
            self._publish_catalog()
            return
        if ctx.phase is ServiceLifecyclePhase.SHUTDOWN:
            self._deregister_if_needed()

    def after(self, ctx: ServiceLifecycleContext) -> None:
        return None

    def _get_registry(self) -> ServiceRegistryProtocol:
        if self._registry is None:
            self._registry = ConsulRegistry(self._config)
        return self._registry

    @staticmethod
    def _build_service_id(config: ServiceRegistryConfig) -> str:
        if config.instance_id:
            return config.instance_id
        return f"{config.service_name}-{config.service_host}-{config.service_port}"

    def _build_registration(self) -> ServiceRegistration:
        health_check: HealthCheck | None = None
        if self._health_check_endpoint:
            health_check = HealthCheck(
                http_endpoint=self._health_check_endpoint,
                interval_seconds=self._config.health_check_interval,
                timeout_seconds=self._config.health_check_timeout,
            )
        meta = {
            "version": self._config.service_version,
        }
        if self._config.instance_id:
            meta["instance_id"] = self._config.instance_id
        return ServiceRegistration(
            service_name=self._config.service_name,
            service_id=self._service_id,
            host=self._config.service_host,
            port=self._config.service_port,
            meta=meta,
            health_check=health_check,
        )

    def _register_if_needed(self) -> None:
        if self._registered:
            return
        registry = self._get_registry()
        registry.register(self._build_registration())
        self._registered = True
        _EVENT_LOGGER.info(
            "Registered service %s",
            self._service_id,
            logger=_LOGGER,
        )

    def _deregister_if_needed(self) -> None:
        if not self._registered:
            return
        registry = self._get_registry()
        registry.deregister(self._service_id)
        self._delete_catalog()
        self._registered = False
        _EVENT_LOGGER.info(
            "Deregistered service %s",
            self._service_id,
            logger=_LOGGER,
        )

    def _publish_catalog(self) -> None:
        publish_algorithm_catalog(
            registry=self._get_registry(),
            config=self._config,
            algorithm_registry=self._algorithm_registry,
            kv_key=self._kv_key,
        )

    def _delete_catalog(self) -> None:
        key = _build_catalog_kv_key(self._config, self._kv_key)
        try:
            self._get_registry().delete_kv(key)
        except Exception:
            _EVENT_LOGGER.exception(
                "Failed to delete registry catalog key %s",
                key,
                logger=_LOGGER,
            )
