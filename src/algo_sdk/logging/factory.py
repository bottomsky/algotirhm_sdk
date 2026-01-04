from __future__ import annotations

from .impl.standard import StandardLoggingConfigurator
from .protocol import LoggingConfiguratorProtocol
from .settings import LoggingSettings, load_logging_settings


def build_logging_configurator(
    settings: LoggingSettings | None = None,
) -> LoggingConfiguratorProtocol:
    resolved = settings or load_logging_settings()
    return StandardLoggingConfigurator(resolved)


def configure_logging(
    settings: LoggingSettings | None = None,
) -> LoggingConfiguratorProtocol:
    configurator = build_logging_configurator(settings)
    configurator.configure()
    return configurator
