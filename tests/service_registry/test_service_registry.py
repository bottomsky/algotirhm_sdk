"""Tests for service registry module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


from algo_sdk import (
    ConsulRegistry,
    HealthCheck,
    MemoryRegistry,
    ServiceRegistration,
    ServiceRegistryProtocol,
    ServiceRegistryConfig,
    ServiceStatus,
    load_config,
)


class TestServiceRegistryConfig:
    """Tests for ServiceRegistryConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = ServiceRegistryConfig()
            assert config.host == "http://127.0.0.1:8500"
            assert config.enabled is False
            assert config.service_name == "algo-core-service"
            assert config.service_port == 8000

    def test_from_environment(self) -> None:
        """Test loading configuration from environment."""
        env = {
            "SERVICE_REGISTRY_HOST": "http://consul.example.com:8500",
            "SERVICE_REGISTRY_ENABLED": "true",
            "SERVICE_NAME": "test-service",
            "SERVICE_PORT": "9000",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.host == "http://consul.example.com:8500"
            assert config.enabled is True
            assert config.service_name == "test-service"
            assert config.service_port == 9000


class TestServiceRegistration:
    """Tests for ServiceRegistration."""

    def test_basic_registration(self) -> None:
        """Test creating a basic service registration."""
        reg = ServiceRegistration(
            service_name="my-service",
            service_id="my-service-1",
            host="192.168.1.10",
            port=8080,
        )
        assert reg.service_name == "my-service"
        assert reg.service_id == "my-service-1"
        assert reg.host == "192.168.1.10"
        assert reg.port == 8080
        assert reg.tags == ()
        assert reg.meta == {}
        assert reg.health_check is None

    def test_registration_with_health_check(self) -> None:
        """Test service registration with health check."""
        check = HealthCheck(
            http_endpoint="/healthz",
            interval_seconds=15,
            timeout_seconds=3,
        )
        reg = ServiceRegistration(
            service_name="my-service",
            service_id="my-service-1",
            host="192.168.1.10",
            port=8080,
            health_check=check,
        )
        assert reg.health_check is not None
        assert reg.health_check.http_endpoint == "/healthz"
        assert reg.health_check.interval_seconds == 15


def test_memory_registry_implements_protocol() -> None:
    registry = MemoryRegistry()
    assert isinstance(registry, ServiceRegistryProtocol)


class TestConsulRegistry:
    """Tests for ConsulRegistry."""

    def test_initialization(self) -> None:
        """Test ConsulRegistry initialization."""
        config = ServiceRegistryConfig(
            host="http://localhost:8500",
            enabled=True,
        )
        registry = ConsulRegistry(config)
        assert registry.config.host == "http://localhost:8500"

    def test_build_registration_payload(self) -> None:
        """Test building Consul registration payload."""
        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        reg = ServiceRegistration(
            service_name="test-service",
            service_id="test-service-1",
            host="127.0.0.1",
            port=8000,
            tags=("v1", "test"),
            meta={"version": "1.0.0"},
        )

        payload = registry._build_registration_payload(reg)

        assert payload["ID"] == "test-service-1"
        assert payload["Name"] == "test-service"
        assert payload["Address"] == "127.0.0.1"
        assert payload["Port"] == 8000
        assert payload["Tags"] == ["v1", "test"]
        assert payload["Meta"] == {"version": "1.0.0"}

    def test_build_check_payload(self) -> None:
        """Test building health check payload."""
        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        check = HealthCheck(
            http_endpoint="/healthz",
            interval_seconds=10,
            timeout_seconds=5,
            deregister_after_seconds=60,
        )

        payload = registry._build_check_payload(check, "127.0.0.1", 8000)

        assert payload["HTTP"] == "http://127.0.0.1:8000/healthz"
        assert payload["Interval"] == "10s"
        assert payload["Timeout"] == "5s"
        assert payload["DeregisterCriticalServiceAfter"] == "60s"

    @patch.object(ConsulRegistry, "_http_get")
    def test_is_healthy_success(self, mock_get: MagicMock) -> None:
        """Test health check when Consul is healthy."""
        mock_get.return_value = ['"127.0.0.1:8300"']

        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        assert registry.is_healthy() is True

    @patch.object(ConsulRegistry, "_http_get")
    def test_is_healthy_failure(self, mock_get: MagicMock) -> None:
        """Test health check when Consul is not available."""
        mock_get.side_effect = Exception("Connection refused")

        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        assert registry.is_healthy() is False

    def test_parse_service_instances(self) -> None:
        """Test parsing Consul catalog service response."""
        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        data = [{
            "ServiceID": "service-1",
            "ServiceName": "my-service",
            "ServiceAddress": "192.168.1.10",
            "ServicePort": 8080,
            "ServiceTags": ["v1"],
            "ServiceMeta": {
                "env": "prod"
            },
        }]

        instances = registry._parse_service_instances(data)

        assert len(instances) == 1
        assert instances[0].service_id == "service-1"
        assert instances[0].service_name == "my-service"
        assert instances[0].host == "192.168.1.10"
        assert instances[0].port == 8080
        assert instances[0].tags == ("v1", )
        assert instances[0].meta == {"env": "prod"}
        assert instances[0].status == ServiceStatus.UNKNOWN

    def test_parse_health_service_instances(self) -> None:
        """Test parsing Consul health service response."""
        config = ServiceRegistryConfig(host="http://localhost:8500")
        registry = ConsulRegistry(config)

        data = [{
            "Service": {
                "ID": "service-1",
                "Service": "my-service",
                "Address": "192.168.1.10",
                "Port": 8080,
                "Tags": ["v1"],
                "Meta": {
                    "env": "prod"
                },
            }
        }]

        instances = registry._parse_health_service_instances(data)

        assert len(instances) == 1
        assert instances[0].service_id == "service-1"
        assert instances[0].status == ServiceStatus.PASSING
