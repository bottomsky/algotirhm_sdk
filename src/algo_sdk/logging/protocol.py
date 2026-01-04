from __future__ import annotations

from typing import Protocol


class LoggingConfiguratorProtocol(Protocol):
    """Protocol for logging configurators."""

    def configure(self) -> None:
        """Apply logging configuration."""
