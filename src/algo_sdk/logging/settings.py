from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    error_dir: str | None
    payload_dir: str | None
    general_dir: str | None
    general_enabled: bool
    level: int
    rotate_when: str
    backup_count: int
    console_enabled: bool

    @classmethod
    def from_env(cls) -> "LoggingSettings":
        level_name = _get_env_str("LOG_LEVEL", "INFO").upper()
        level = _parse_level(level_name)
        rotate_when = _get_env_str("LOG_ROTATE_WHEN", "midnight")
        backup_count = _get_env_int("LOG_BACKUP_COUNT", 14)
        general_enabled = _get_env_bool("LOG_GENERAL_ENABLED", False)
        console_enabled = _get_env_bool("LOG_CONSOLE_ENABLED", True)
        error_dir = _get_env_path("LOG_ERROR_DIR", "logs/error")
        payload_dir = _get_env_path("LOG_PAYLOAD_DIR", "logs/payload")
        general_dir = _get_env_path("LOG_GENERAL_DIR", "logs/general")
        if not general_enabled:
            general_dir = None
        return cls(
            error_dir=error_dir,
            payload_dir=payload_dir,
            general_dir=general_dir,
            general_enabled=general_enabled,
            level=level,
            rotate_when=rotate_when,
            backup_count=backup_count,
            console_enabled=console_enabled,
        )


def load_logging_settings() -> LoggingSettings:
    return LoggingSettings.from_env()


def _parse_level(level_name: str) -> int:
    level = logging.getLevelName(level_name)
    if isinstance(level, int):
        return level
    raise ValueError(f"Invalid LOG_LEVEL: {level_name!r}")


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid bool env var {name}={value!r}")


def _get_env_path(name: str, default: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return None
    return value
