"""Service registry error definitions."""

from __future__ import annotations


class ServiceRegistryError(Exception):
    """Base exception for service registry errors."""


class ServiceRegistrationError(ServiceRegistryError):
    """Error during service registration."""


class ServiceDeregistrationError(ServiceRegistryError):
    """Error during service deregistration."""


class ServiceDiscoveryError(ServiceRegistryError):
    """Error during service discovery."""


class ServiceRegistryConnectionError(ServiceRegistryError):
    """Error connecting to service registry."""


class KVOperationError(ServiceRegistryError):
    """Error during key-value operations."""
