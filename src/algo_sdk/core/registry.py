from __future__ import annotations

import importlib
import inspect
import logging
import pickle
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any, TypeVar, cast, get_type_hints

import yaml
from pydantic import BaseModel as _PydanticBaseModel

from .base_model_impl import BaseModel
from .errors import AlgorithmNotFoundError, AlgorithmRegistrationError
from .lifecycle import BaseAlgorithm
from .metadata import (
    AlgorithmMarker,
    AlgorithmSpec,
    AlgorithmType,
    ExecutionConfig,
    ExecutionMode,
    HyperParams,
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
                    f"algorithm not found: {name} ({version})"
                ) from exc

    def list(self) -> Iterable[AnySpec]:
        with self._lock:
            return tuple(self._items.values())

    def register_from_module(self, module: ModuleType) -> None:
        exports = getattr(module, "__all__", None)
        if not isinstance(exports, (list, tuple)):
            _LOGGER.warning(
                "Module %s has no __all__ exports; skipping",
                module.__name__,
            )
            return

        for name in exports:
            if not isinstance(name, str):
                _LOGGER.warning(
                    "Module %s has non-string __all__ entry: %r",
                    module.__name__,
                    name,
                )
                continue
            obj = getattr(module, name, None)
            if obj is None:
                _LOGGER.warning(
                    "Module %s missing __all__ export %s",
                    module.__name__,
                    name,
                )
                continue
            if not inspect.isclass(obj):
                _LOGGER.warning(
                    "Skipping %s from %s: not a class",
                    name,
                    module.__name__,
                )
                continue
            if not issubclass(obj, BaseAlgorithm):
                _LOGGER.warning(
                    "Skipping %s from %s: not a BaseAlgorithm",
                    name,
                    module.__name__,
                )
                continue
            marker = getattr(obj, "__algo_meta__", None)
            if not isinstance(marker, AlgorithmMarker):
                _LOGGER.warning(
                    "Skipping %s from %s: missing algorithm marker",
                    name,
                    module.__name__,
                )
                continue
            try:
                spec = self._build_spec_from_marker(obj, marker)
                self.register(spec)
            except AlgorithmRegistrationError as exc:
                _LOGGER.warning(
                    "Algorithm %s already registered: %s",
                    name,
                    exc,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to register algorithm %s from %s",
                    name,
                    module.__name__,
                )

    def load_packages_from_dir(self, path: str | Path) -> None:
        base_dir = Path(path)
        if not base_dir.exists():
            _LOGGER.warning(
                "Algorithm module directory not found: %s", base_dir
            )
            return
        if not base_dir.is_dir():
            _LOGGER.warning(
                "Algorithm module path is not a directory: %s", base_dir
            )
            return

        resolved = base_dir.resolve()
        resolved_str = str(resolved)
        if resolved_str not in sys.path:
            sys.path.insert(0, resolved_str)

        for package_dir in sorted(resolved.iterdir()):
            if not package_dir.is_dir():
                continue
            if not (package_dir / "__init__.py").exists():
                continue
            package_name = package_dir.name
            try:
                module = importlib.import_module(package_name)
            except Exception:
                _LOGGER.exception(
                    "Failed to import algorithm package %s from %s",
                    package_name,
                    resolved,
                )
                continue
            self.register_from_module(module)

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

    def _build_spec_from_marker(
        self,
        target_cls: type[BaseAlgorithm[BaseModel, BaseModel]],
        marker: AlgorithmMarker,
    ) -> AlgorithmSpec[BaseModel, BaseModel]:
        run_method: object = getattr(target_cls, "run", None)
        if run_method is None or not callable(run_method):
            raise ValueError("algorithm class missing callable 'run' method")
        if getattr(run_method, "__isabstractmethod__", False):
            raise ValueError("algorithm class must implement 'run'")
        if inspect.isabstract(target_cls):
            raise ValueError("algorithm class must not be abstract")

        input_model, output_model, inferred_hyperparams = self._extract_io(
            run_method
        )

        exec_config = self._build_execution_config(marker.execution)
        log_config = self._build_logging_config(marker.logging)

        self._assert_picklable(target_cls, label="algorithm entrypoint")
        self._assert_picklable(input_model, label="algorithm input model")
        self._assert_picklable(output_model, label="algorithm output model")
        if inferred_hyperparams is not None:
            self._assert_picklable(
                inferred_hyperparams,
                label="algorithm hyperparams model",
            )

        return AlgorithmSpec(
            name=marker.name,
            version=marker.version,
            algorithm_type=marker.algorithm_type,
            description=marker.description,
            created_time=marker.created_time,
            author=marker.author,
            category=marker.category,
            input_model=input_model,
            output_model=output_model,
            application_scenarios=marker.application_scenarios,
            extra=dict(marker.extra),
            execution=exec_config,
            logging=log_config,
            hyperparams_model=inferred_hyperparams,
            entrypoint=target_cls,
            is_class=True,
        )

    def _load_overrides_from_dir(
        self, path: Path
    ) -> list[tuple[OverrideKey, dict[str, object]]]:
        if not path.exists():
            _LOGGER.warning("Algorithm metadata directory not found: %s", path)
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
        algorithm_type = self._parse_algorithm_type(algorithm_type_raw, source)
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

    def _build_execution_config(
        self, execution: Mapping[str, object] | None
    ) -> ExecutionConfig:
        if not execution:
            return ExecutionConfig()

        allowed_keys = {
            "execution_mode",
            "stateful",
            "isolated_pool",
            "max_workers",
            "timeout_s",
            "gpu",
        }
        unknown = set(execution.keys()) - allowed_keys
        if unknown:
            raise ValueError(
                f"unknown execution keys: {', '.join(sorted(unknown))}"
            )

        execution_mode = execution.get(
            "execution_mode", ExecutionMode.PROCESS_POOL
        )
        if isinstance(execution_mode, str):
            execution_mode = ExecutionMode(execution_mode)
        if not isinstance(execution_mode, ExecutionMode):
            raise ValueError("execution_mode must be an ExecutionMode value")

        stateful = execution.get("stateful", False)
        if not isinstance(stateful, bool):
            raise ValueError("stateful must be a bool")

        isolated_pool = execution.get("isolated_pool", False)
        if not isinstance(isolated_pool, bool):
            raise ValueError("isolated_pool must be a bool")

        max_workers = execution.get("max_workers")
        if max_workers is not None and not isinstance(max_workers, int):
            raise ValueError("max_workers must be an int")

        timeout_s = execution.get("timeout_s")
        if timeout_s is not None and not isinstance(timeout_s, int):
            raise ValueError("timeout_s must be an int")

        gpu = execution.get("gpu")
        if gpu is not None and not isinstance(gpu, str):
            raise ValueError("gpu must be a str")

        return ExecutionConfig(
            execution_mode=execution_mode,
            stateful=stateful,
            isolated_pool=isolated_pool,
            max_workers=max_workers,
            timeout_s=timeout_s,
            gpu=gpu,
        )

    def _build_logging_config(
        self, logging_config: Mapping[str, object] | None
    ) -> LoggingConfig:
        if not logging_config:
            return LoggingConfig()

        allowed_keys = {
            "enabled",
            "log_input",
            "log_output",
            "on_error_only",
            "sample_rate",
            "max_length",
            "redact_fields",
        }
        unknown = set(logging_config.keys()) - allowed_keys
        if unknown:
            raise ValueError(
                f"unknown logging keys: {', '.join(sorted(unknown))}"
            )

        enabled = logging_config.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a bool")

        log_input = logging_config.get("log_input", False)
        if not isinstance(log_input, bool):
            raise ValueError("log_input must be a bool")

        log_output = logging_config.get("log_output", False)
        if not isinstance(log_output, bool):
            raise ValueError("log_output must be a bool")

        on_error_only = logging_config.get("on_error_only", False)
        if not isinstance(on_error_only, bool):
            raise ValueError("on_error_only must be a bool")

        sample_rate = logging_config.get("sample_rate", 1.0)
        if not isinstance(sample_rate, (int, float)):
            raise ValueError("sample_rate must be a number")
        sample_rate = float(sample_rate)
        if sample_rate < 0 or sample_rate > 1:
            raise ValueError("sample_rate must be between 0 and 1")

        max_length = logging_config.get("max_length", 2048)
        if not isinstance(max_length, int):
            raise ValueError("max_length must be an int")
        if max_length < 0:
            raise ValueError("max_length must be non-negative")

        redact_fields = logging_config.get("redact_fields", ())
        if isinstance(redact_fields, str):
            raise ValueError("redact_fields must be a list of str")
        if not isinstance(redact_fields, (list, tuple, set)):
            raise ValueError("redact_fields must be a list of str")
        redact_tuple: tuple[str, ...] = tuple(
            str(field) for field in redact_fields
        )

        return LoggingConfig(
            enabled=enabled,
            log_input=log_input,
            log_output=log_output,
            on_error_only=on_error_only,
            sample_rate=sample_rate,
            max_length=max_length,
            redact_fields=redact_tuple,
        )

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

    def _assert_picklable(self, obj: object, *, label: str) -> None:
        qualname = getattr(obj, "__qualname__", None)
        module_name = getattr(obj, "__module__", None)
        obj_name = getattr(obj, "__name__", None)
        if (
            module_name
            and obj_name
            and qualname
            and qualname == obj_name
            and "<locals>" not in qualname
        ):
            module = sys.modules.get(module_name)
            if module is not None and not hasattr(module, obj_name):
                setattr(module, obj_name, obj)
        try:
            pickle.dumps(obj)
        except Exception as exc:
            module = getattr(obj, "__module__", None)
            hint = (
                "Entrypoint and model types must be defined at module top "
                "level (not inside a function), and must be importable by "
                "module path. Avoid lambdas/closures/local classes."
            )
            details = (
                f"{label} is not picklable"
                f" (module={module!r}, qualname={qualname!r}): {exc}"
            )
            raise ValueError(f"{details}. {hint}") from exc

    def _extract_io(
        self,
        callable_obj: object,
        *,
        skip_first: bool = True,
    ) -> tuple[type[BaseModel], type[BaseModel], type[HyperParams] | None]:
        sig = inspect.signature(callable_obj)
        params = list(sig.parameters.values())
        if skip_first and params:
            params = params[1:]

        if len(params) not in (1, 2):
            raise ValueError(
                "run method must accept one or two arguments (besides self)"
            )

        param = params[0]
        type_hints = get_type_hints(callable_obj, include_extras=False)
        annotation: object = type_hints.get(
            param.name, param.annotation  # pyright: ignore[reportAny]
        )
        if annotation is inspect.Signature.empty:
            raise ValueError(
                "input must be type-annotated with a BaseModel subclass"
            )
        if not (
            inspect.isclass(annotation)
            and issubclass(annotation, _PydanticBaseModel)
        ):
            raise ValueError("algorithm input must be a BaseModel subclass")

        hyperparams_model: type[HyperParams] | None = None
        if len(params) == 2:
            hyper_param = params[1]
            hyper_annotation: object = type_hints.get(
                hyper_param.name, hyper_param.annotation
            )
            if hyper_annotation is inspect.Signature.empty:
                raise ValueError(
                    "hyperparams must be type-annotated with a "
                    "HyperParams subclass"
                )
            if not (
                inspect.isclass(hyper_annotation)
                and issubclass(hyper_annotation, HyperParams)
            ):
                raise ValueError("hyperparams must be a HyperParams subclass")
            hyperparams_model = hyper_annotation  # type: ignore[assignment]

        ret_anno = sig.return_annotation  # pyright: ignore[reportAny]
        output_annotation: object = type_hints.get("return", ret_anno)
        if output_annotation is inspect.Signature.empty:
            raise ValueError(
                "output must be type-annotated with a BaseModel subclass"
            )
        if not (
            inspect.isclass(output_annotation)
            and issubclass(output_annotation, _PydanticBaseModel)
        ):
            raise ValueError("algorithm output must be a BaseModel subclass")

        return (
            annotation,
            output_annotation,
            hyperparams_model,
        )  # type: ignore[return-value]


_default_registry = AlgorithmRegistry()


def get_registry() -> AlgorithmRegistry:
    return _default_registry
