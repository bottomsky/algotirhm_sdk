from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date
import logging
from pathlib import Path
import re
from threading import RLock
from typing import Any, TypeVar, cast

import yaml

from .base_model_impl import BaseModel
from .errors import AlgorithmNotFoundError, AlgorithmRegistrationError
from .metadata import (
    AlgorithmSpec,
    AlgorithmType,
    ExecutionConfig,
    ExecutionMode,
    LoggingConfig,
)

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)
AnySpec = AlgorithmSpec[Any, Any]

_LOGGER = logging.getLogger(__name__)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OverrideKey = tuple[str, str, str, AlgorithmType]


class AlgorithmRegistry:
    """In-memory registry for algorithms."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AnySpec] = {}
        self._overrides: dict[OverrideKey, dict[str, object]] = {}
        self._lock = RLock()

    def register(self, spec: AlgorithmSpec[Req, Resp]) -> None:
        key = spec.key()
        with self._lock:
            if key in self._items:
                raise AlgorithmRegistrationError(
                    f"algorithm already registered: {spec.name} "
                    f"({spec.version})"
                )
            # Cast to a common storage type since AlgorithmSpec is invariant.
            self._apply_overrides(spec)
            self._items[key] = cast(AnySpec, spec)

    def get(self, name: str, version: str) -> AnySpec:
        key = (name, version)
        with self._lock:
            try:
                return self._items[key]
            except KeyError as exc:
                raise AlgorithmNotFoundError(
                    f"algorithm not found: {name} ({version})") from exc

    def list(self) -> Iterable[AnySpec]:
        with self._lock:
            return tuple(self._items.values())

    def load_config(self, path: str | Path) -> None:
        overrides = self._load_overrides_from_dir(Path(path))
        if not overrides:
            return
        with self._lock:
            for key, override in overrides:
                self._overrides[key] = override
            for spec in self._items.values():
                self._apply_overrides(spec)

    def _apply_overrides(self, spec: AlgorithmSpec[Req, Resp]) -> None:
        key = (spec.name, spec.version, spec.category, spec.algorithm_type)
        override = self._overrides.get(key)
        if not override:
            return

        if "description" in override:
            spec.description = cast(str, override["description"])
        if "created_time" in override:
            spec.created_time = cast(str, override["created_time"])
        if "author" in override:
            spec.author = cast(str, override["author"])
        if "application_scenarios" in override:
            spec.application_scenarios = cast(
                str, override["application_scenarios"]
            )
        if "extra" in override:
            extra = cast(dict[str, str], override["extra"])
            spec.extra = {**spec.extra, **extra}
        if "logging" in override:
            spec.logging = self._merge_logging(
                spec.logging,
                cast(Mapping[str, object], override["logging"]),
            )
        if "execution" in override:
            spec.execution = self._merge_execution(
                spec.execution,
                cast(Mapping[str, object], override["execution"]),
            )

    def _load_overrides_from_dir(
        self, path: Path
    ) -> list[tuple[OverrideKey, dict[str, object]]]:
        if not path.exists():
            _LOGGER.warning(
                "Algorithm metadata directory not found: %s", path
            )
            return []
        if not path.is_dir():
            _LOGGER.warning(
                "Algorithm metadata path is not a directory: %s", path
            )
            return []

        overrides: list[tuple[OverrideKey, dict[str, object]]] = []
        for file_path in sorted(path.glob("*.algometa.yaml")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                _LOGGER.warning(
                    "Failed to read algorithm metadata file: %s",
                    file_path,
                    exc_info=True,
                )
                continue
            try:
                payload = yaml.safe_load(content)
            except Exception:
                _LOGGER.warning(
                    "Failed to parse algorithm metadata file: %s",
                    file_path,
                    exc_info=True,
                )
                continue
            if payload is None:
                continue
            if not isinstance(payload, list):
                _LOGGER.warning(
                    "Algorithm metadata file must contain a list: %s",
                    file_path,
                )
                continue

            for entry in payload:
                if not isinstance(entry, Mapping):
                    _LOGGER.warning(
                        "Algorithm metadata entry must be a mapping: %s",
                        file_path,
                    )
                    continue
                parsed = self._parse_override_entry(
                    entry, source=str(file_path)
                )
                if parsed is not None:
                    overrides.append(parsed)
        return overrides

    def _parse_override_entry(
        self,
        entry: Mapping[str, object],
        *,
        source: str,
    ) -> tuple[OverrideKey, dict[str, object]] | None:
        name = self._require_str(entry, "name", source)
        version = self._require_str(entry, "version", source)
        category = self._require_str(entry, "category", source)
        algorithm_type_raw = entry.get("algorithm_type")
        if not name or not version or not category:
            return None
        algorithm_type = self._parse_algorithm_type(
            algorithm_type_raw, source
        )
        if algorithm_type is None:
            return None

        override: dict[str, object] = {}
        allowed_keys = {
            "description",
            "created_time",
            "author",
            "application_scenarios",
            "extra",
            "logging",
            "execution",
        }
        for key, value in entry.items():
            if key in {"name", "version", "category", "algorithm_type"}:
                continue
            if key not in allowed_keys:
                _LOGGER.warning(
                    "Unknown algorithm metadata key %s in %s", key, source
                )
                continue
            if key in {"description", "author", "application_scenarios"}:
                text = self._require_str(entry, key, source)
                if text is None:
                    return None
                override[key] = text
            elif key == "created_time":
                text = self._require_str(entry, key, source)
                if text is None or not self._validate_date(text, source):
                    return None
                override[key] = text
            elif key == "extra":
                extra = self._parse_extra(value, source)
                if extra is None:
                    return None
                override[key] = extra
            elif key == "logging":
                logging_override = self._parse_logging_override(value, source)
                if logging_override is None:
                    return None
                override[key] = logging_override
            elif key == "execution":
                execution_override = self._parse_execution_override(
                    value, source
                )
                if execution_override is None:
                    return None
                override[key] = execution_override

        return (name, version, category, algorithm_type), override

    def _require_str(
        self,
        entry: Mapping[str, object],
        key: str,
        source: str,
    ) -> str | None:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            _LOGGER.warning(
                "Algorithm metadata entry missing %s in %s", key, source
            )
            return None
        return value.strip()

    def _validate_date(self, value: str, source: str) -> bool:
        if not _DATE_RE.fullmatch(value):
            _LOGGER.warning(
                "Algorithm metadata created_time invalid format in %s",
                source,
            )
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            _LOGGER.warning(
                "Algorithm metadata created_time invalid date in %s",
                source,
            )
            return False
        return True

    def _parse_algorithm_type(
        self, value: object, source: str
    ) -> AlgorithmType | None:
        if isinstance(value, AlgorithmType):
            return value
        if isinstance(value, str):
            try:
                return AlgorithmType(value)
            except ValueError:
                _LOGGER.warning(
                    "Algorithm metadata invalid algorithm_type in %s",
                    source,
                )
                return None
        _LOGGER.warning(
            "Algorithm metadata algorithm_type must be a string in %s",
            source,
        )
        return None

    def _parse_extra(
        self, value: object, source: str
    ) -> dict[str, str] | None:
        if not isinstance(value, Mapping):
            _LOGGER.warning(
                "Algorithm metadata extra must be a mapping in %s", source
            )
            return None
        extra: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not isinstance(item, str):
                _LOGGER.warning(
                    "Algorithm metadata extra must be str pairs in %s",
                    source,
                )
                return None
            extra[key] = item
        return extra

    def _parse_logging_override(
        self, value: object, source: str
    ) -> dict[str, object] | None:
        if not isinstance(value, Mapping):
            _LOGGER.warning(
                "Algorithm metadata logging must be a mapping in %s", source
            )
            return None
        allowed_keys = {
            "enabled",
            "log_input",
            "log_output",
            "on_error_only",
            "sample_rate",
            "max_length",
            "redact_fields",
        }
        override: dict[str, object] = {}
        for key, item in value.items():
            if key not in allowed_keys:
                _LOGGER.warning(
                    "Unknown logging override key %s in %s", key, source
                )
                continue
            if key in {"enabled", "log_input", "log_output", "on_error_only"}:
                if not isinstance(item, bool):
                    _LOGGER.warning(
                        "Logging override %s must be bool in %s",
                        key,
                        source,
                    )
                    return None
                override[key] = item
            elif key == "sample_rate":
                if not isinstance(item, (int, float)):
                    _LOGGER.warning(
                        "Logging override sample_rate must be number in %s",
                        source,
                    )
                    return None
                sample_rate = float(item)
                if sample_rate < 0 or sample_rate > 1:
                    _LOGGER.warning(
                        "Logging override sample_rate out of range in %s",
                        source,
                    )
                    return None
                override[key] = sample_rate
            elif key == "max_length":
                if not isinstance(item, int) or item < 0:
                    _LOGGER.warning(
                        "Logging override max_length invalid in %s", source
                    )
                    return None
                override[key] = item
            elif key == "redact_fields":
                if isinstance(item, str) or not isinstance(
                    item, (list, tuple, set)
                ):
                    _LOGGER.warning(
                        "Logging override redact_fields must be list in %s",
                        source,
                    )
                    return None
                override[key] = tuple(str(field) for field in item)
        return override

    def _parse_execution_override(
        self, value: object, source: str
    ) -> dict[str, object] | None:
        if not isinstance(value, Mapping):
            _LOGGER.warning(
                "Algorithm metadata execution must be a mapping in %s", source
            )
            return None
        allowed_keys = {
            "execution_mode",
            "stateful",
            "isolated_pool",
            "max_workers",
            "timeout_s",
            "gpu",
        }
        override: dict[str, object] = {}
        for key, item in value.items():
            if key not in allowed_keys:
                _LOGGER.warning(
                    "Unknown execution override key %s in %s", key, source
                )
                continue
            if key == "execution_mode":
                if isinstance(item, ExecutionMode):
                    override[key] = item
                elif isinstance(item, str):
                    try:
                        override[key] = ExecutionMode(item)
                    except ValueError:
                        _LOGGER.warning(
                            "Execution override execution_mode invalid in %s",
                            source,
                        )
                        return None
                else:
                    _LOGGER.warning(
                        "Execution override execution_mode invalid in %s",
                        source,
                    )
                    return None
            elif key in {"stateful", "isolated_pool"}:
                if not isinstance(item, bool):
                    _LOGGER.warning(
                        "Execution override %s must be bool in %s",
                        key,
                        source,
                    )
                    return None
                override[key] = item
            elif key in {"max_workers", "timeout_s"}:
                if item is not None and not isinstance(item, int):
                    _LOGGER.warning(
                        "Execution override %s must be int in %s",
                        key,
                        source,
                    )
                    return None
                override[key] = item
            elif key == "gpu":
                if item is not None and not isinstance(item, str):
                    _LOGGER.warning(
                        "Execution override gpu must be str in %s", source
                    )
                    return None
                override[key] = item
        return override

    def _merge_logging(
        self, current: LoggingConfig, override: Mapping[str, object]
    ) -> LoggingConfig:
        kwargs: dict[str, object] = {}
        if "enabled" in override:
            kwargs["enabled"] = override["enabled"]
        if "log_input" in override:
            kwargs["log_input"] = override["log_input"]
        if "log_output" in override:
            kwargs["log_output"] = override["log_output"]
        if "on_error_only" in override:
            kwargs["on_error_only"] = override["on_error_only"]
        if "sample_rate" in override:
            kwargs["sample_rate"] = override["sample_rate"]
        if "max_length" in override:
            kwargs["max_length"] = override["max_length"]
        if "redact_fields" in override:
            kwargs["redact_fields"] = override["redact_fields"]
        return replace(current, **kwargs)

    def _merge_execution(
        self, current: ExecutionConfig, override: Mapping[str, object]
    ) -> ExecutionConfig:
        kwargs: dict[str, object] = {}
        if "execution_mode" in override:
            kwargs["execution_mode"] = override["execution_mode"]
        if "stateful" in override:
            kwargs["stateful"] = override["stateful"]
        if "isolated_pool" in override:
            kwargs["isolated_pool"] = override["isolated_pool"]
        if "max_workers" in override:
            kwargs["max_workers"] = override["max_workers"]
        if "timeout_s" in override:
            kwargs["timeout_s"] = override["timeout_s"]
        if "gpu" in override:
            kwargs["gpu"] = override["gpu"]
        return replace(current, **kwargs)


_default_registry = AlgorithmRegistry()


def get_registry() -> AlgorithmRegistry:
    return _default_registry
