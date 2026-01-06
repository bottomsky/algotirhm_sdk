"""Algorithm decorator for class-based algorithms."""

from __future__ import annotations

import inspect
import pickle
import re
import sys
from datetime import date
from typing import Callable, get_type_hints

from pydantic import BaseModel as _PydanticBaseModel

from algo_sdk.core import (
    AlgorithmSpec,
    AlgorithmValidationError,
    BaseModel,
    HyperParams,
    ExecutionConfig,
    ExecutionMode,
    LoggingConfig,
    get_registry,
    AlgorithmLifecycleProtocol,
    AlgorithmType,
)
from algo_sdk.core.registry import AlgorithmRegistry


class DefaultAlgorithmDecorator:
    """Decorator used to register class-based algorithms."""

    _registry: AlgorithmRegistry

    def __init__(self, *, registry: AlgorithmRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def __call__(
        self,
        *,
        name: str,
        version: str,
        algorithm_type: AlgorithmType | str,
        description: str | None = None,
        created_time: str | None = None,
        author: str | None = None,
        category: str | None = None,
        application_scenarios: str | None = None,
        extra: dict[str, str] | None = None,
        execution: dict[str, object] | None = None,
        logging: LoggingConfig | dict[str, object] | None = None,
    ) -> Callable[
        [type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]]],
        type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]],
    ]:
        """Register a class-based algorithm.

        Args:
            name: Algorithm name
            version: Algorithm version
            algorithm_type: Required algorithm type (Planning, Prepare,
                Prediction)
            description: Optional description
            created_time: Required created date (YYYY-MM-DD)
            author: Required author name
            category: Required category name
            application_scenarios: Optional application scenario string
            extra: Optional string key/value metadata
            execution: Optional execution config dict
            logging: Optional logging config (dict or LoggingConfig)
        Returns:
            A decorator that preserves the type of the decorated class
        """
        if not name or not version:
            raise AlgorithmValidationError(
                "name and version are required for registration"
            )

        if isinstance(algorithm_type, str):
            try:
                algorithm_type = AlgorithmType(algorithm_type)
            except ValueError:
                raise AlgorithmValidationError(
                    f"Invalid algorithm_type: {algorithm_type}. "
                    f"Must be one of {[t.value for t in AlgorithmType]}"
                )
        if not isinstance(algorithm_type, AlgorithmType):
            raise AlgorithmValidationError(
                "algorithm_type must be an AlgorithmType enum value"
            )

        exec_config = self._build_execution_config(execution)
        log_config = self._build_logging_config(logging)
        (
            created_time,
            author,
            category,
            application_scenarios,
            extra,
        ) = self._validate_metadata(
            created_time=created_time,
            author=author,
            category=category,
            application_scenarios=application_scenarios,
            extra=extra,
        )

        def _decorator(
            target: type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]],
        ) -> type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]]:
            if inspect.isclass(target):
                spec = self._build_class_spec(
                    target,
                    name=name,
                    version=version,
                    algorithm_type=algorithm_type,
                    description=description,
                    created_time=created_time,
                    author=author,
                    category=category,
                    application_scenarios=application_scenarios,
                    extra=extra,
                    exec_config=exec_config,
                    log_config=log_config,
                )
            else:
                raise AlgorithmValidationError(
                    "decorator target must be a class"
                )
            self._registry.register(spec)
            return target

        return _decorator

    def _build_execution_config(
        self, execution: dict[str, object] | None
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
            raise AlgorithmValidationError(
                f"unknown execution keys: {', '.join(sorted(unknown))}"
            )

        execution_mode = execution.get(
            "execution_mode", ExecutionMode.PROCESS_POOL
        )
        if not isinstance(execution_mode, ExecutionMode):
            raise AlgorithmValidationError(
                "execution_mode must be an ExecutionMode enum value"
            )

        stateful = execution.get("stateful", False)
        if not isinstance(stateful, bool):
            raise AlgorithmValidationError("stateful must be a bool")

        isolated_pool = execution.get("isolated_pool", False)
        if not isinstance(isolated_pool, bool):
            raise AlgorithmValidationError("isolated_pool must be a bool")

        max_workers = execution.get("max_workers")
        if max_workers is not None and not isinstance(max_workers, int):
            raise AlgorithmValidationError("max_workers must be an int")

        timeout_s = execution.get("timeout_s")
        if timeout_s is not None and not isinstance(timeout_s, int):
            raise AlgorithmValidationError("timeout_s must be an int")

        gpu = execution.get("gpu")
        if gpu is not None and not isinstance(gpu, str):
            raise AlgorithmValidationError("gpu must be a str")

        return ExecutionConfig(
            execution_mode=execution_mode,
            stateful=stateful,
            isolated_pool=isolated_pool,
            max_workers=max_workers,
            timeout_s=timeout_s,
            gpu=gpu,
        )

    def _build_logging_config(
        self, logging: LoggingConfig | dict[str, object] | None
    ) -> LoggingConfig:
        if not logging:
            return LoggingConfig()
        if isinstance(logging, LoggingConfig):
            return logging

        allowed_keys = {
            "enabled",
            "log_input",
            "log_output",
            "on_error_only",
            "sample_rate",
            "max_length",
            "redact_fields",
        }
        unknown = set(logging.keys()) - allowed_keys
        if unknown:
            raise AlgorithmValidationError(
                f"unknown logging keys: {', '.join(sorted(unknown))}"
            )

        enabled = logging.get("enabled", True)
        if not isinstance(enabled, bool):
            raise AlgorithmValidationError("enabled must be a bool")

        log_input = logging.get("log_input", False)
        if not isinstance(log_input, bool):
            raise AlgorithmValidationError("log_input must be a bool")

        log_output = logging.get("log_output", False)
        if not isinstance(log_output, bool):
            raise AlgorithmValidationError("log_output must be a bool")

        on_error_only = logging.get("on_error_only", False)
        if not isinstance(on_error_only, bool):
            raise AlgorithmValidationError("on_error_only must be a bool")

        sample_rate = logging.get("sample_rate", 1.0)
        if not isinstance(sample_rate, (int, float)):
            raise AlgorithmValidationError("sample_rate must be a number")
        sample_rate = float(sample_rate)
        if sample_rate < 0 or sample_rate > 1:
            raise AlgorithmValidationError(
                "sample_rate must be between 0 and 1"
            )

        max_length = logging.get("max_length", 2048)
        if not isinstance(max_length, int):
            raise AlgorithmValidationError("max_length must be an int")
        if max_length < 0:
            raise AlgorithmValidationError("max_length must be non-negative")

        redact_fields = logging.get("redact_fields", ())
        if isinstance(redact_fields, str):
            raise AlgorithmValidationError(
                "redact_fields must be a list of str"
            )
        if not isinstance(redact_fields, (list, tuple, set)):
            raise AlgorithmValidationError(
                "redact_fields must be a list of str"
            )
        redact_tuple: tuple[str, ...] = tuple(str(f) for f in redact_fields)

        return LoggingConfig(
            enabled=enabled,
            log_input=log_input,
            log_output=log_output,
            on_error_only=on_error_only,
            sample_rate=sample_rate,
            max_length=max_length,
            redact_fields=redact_tuple,
        )

    def _build_class_spec(
        self,
        target_cls: type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]],
        *,
        name: str,
        version: str,
        algorithm_type: AlgorithmType,
        description: str | None,
        created_time: str,
        author: str,
        category: str,
        application_scenarios: str | None,
        extra: dict[str, str],
        exec_config: ExecutionConfig,
        log_config: LoggingConfig,
    ) -> AlgorithmSpec[BaseModel, BaseModel]:
        run_method: object = getattr(target_cls, "run", None)
        if run_method is None or not callable(run_method):
            raise AlgorithmValidationError(
                "class-based algorithm must define a callable 'run' method"
            )
        if getattr(run_method, "__isabstractmethod__", False):
            raise AlgorithmValidationError(
                "class-based algorithm must provide a concrete 'run' method"
            )
        if inspect.isabstract(target_cls):
            raise AlgorithmValidationError(
                "class-based algorithm must not be abstract"
            )

        input_model, output_model, inferred_hyperparams = self._extract_io(
            run_method
        )

        for hook_name in ("initialize", "before_run", "after_run", "shutdown"):
            if not hasattr(target_cls, hook_name):
                raise AlgorithmValidationError(
                    f"hook '{hook_name}' must be implemented"
                )
            hook = getattr(target_cls, hook_name)  # pyright: ignore[reportAny]
            if hook is not None and not callable(
                hook
            ):  # pyright: ignore[reportAny]
                raise AlgorithmValidationError(
                    f"hook '{hook_name}' must be callable or absent"
                )

        self._assert_picklable(target_cls, label="algorithm entrypoint")
        self._assert_picklable(input_model, label="algorithm input model")
        self._assert_picklable(output_model, label="algorithm output model")
        if inferred_hyperparams is not None:
            self._assert_picklable(
                inferred_hyperparams,
                label="algorithm hyperparams model",
            )

        return AlgorithmSpec(
            name=name,
            version=version,
            algorithm_type=algorithm_type,
            description=description,
            created_time=created_time,
            author=author,
            category=category,
            input_model=input_model,
            output_model=output_model,
            application_scenarios=application_scenarios,
            extra=extra,
            execution=exec_config,
            logging=log_config,
            hyperparams_model=inferred_hyperparams,
            entrypoint=target_cls,
            is_class=True,
        )

    def _validate_metadata(
        self,
        *,
        created_time: str | None,
        author: str | None,
        category: str | None,
        application_scenarios: str | None,
        extra: dict[str, str] | None,
    ) -> tuple[str, str, str, str | None, dict[str, str]]:
        if not created_time or not created_time.strip():
            raise AlgorithmValidationError("created_time is required")
        created_time = created_time.strip()
        if not self._DATE_RE.fullmatch(created_time):
            raise AlgorithmValidationError(
                "created_time must be in YYYY-MM-DD format"
            )
        try:
            date.fromisoformat(created_time)
        except ValueError as exc:
            raise AlgorithmValidationError(
                "created_time must be a valid date"
            ) from exc

        if not author or not author.strip():
            raise AlgorithmValidationError("author is required")
        author = author.strip()

        if not category or not category.strip():
            raise AlgorithmValidationError("category is required")
        category = category.strip()

        if application_scenarios is not None:
            if not isinstance(application_scenarios, str):
                raise AlgorithmValidationError(
                    "application_scenarios must be a str"
                )
            if not application_scenarios.strip():
                raise AlgorithmValidationError(
                    "application_scenarios must be non-empty"
                )
            application_scenarios = application_scenarios.strip()

        if extra is None:
            extra = {}
        elif not isinstance(extra, dict):
            raise AlgorithmValidationError("extra must be a dict[str, str]")
        else:
            for key, value in extra.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise AlgorithmValidationError(
                        "extra must be a dict[str, str]"
                    )

        return (
            created_time,
            author,
            category,
            application_scenarios,
            extra,
        )

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
            raise AlgorithmValidationError(f"{details}. {hint}") from exc

    def _extract_io(
        self,
        callable_obj: Callable[..., object],
        *,
        skip_first: bool = True,
    ) -> tuple[type[BaseModel], type[BaseModel], type[HyperParams] | None]:
        """Extract input/output models from callable signature.

        Args:
            run_method: The run method of the algorithm class

        Returns:
            Tuple of (input_model, output_model, hyperparams_model) types
        """
        sig = inspect.signature(callable_obj)
        params = list(sig.parameters.values())
        if skip_first and params:
            params = params[1:]

        if len(params) not in (1, 2):
            raise AlgorithmValidationError(
                "run method must accept one or two arguments (besides self)"
            )

        param = params[0]
        type_hints = get_type_hints(callable_obj, include_extras=False)
        annotation: object = type_hints.get(
            param.name, param.annotation  # pyright: ignore[reportAny]
        )
        if annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "input must be type-annotated with a BaseModel subclass"
            )
        if not (
            inspect.isclass(annotation)
            and issubclass(annotation, _PydanticBaseModel)
        ):
            raise AlgorithmValidationError(
                "algorithm input must be a BaseModel subclass"
            )

        hyperparams_model: type[HyperParams] | None = None
        if len(params) == 2:
            hyper_param = params[1]
            hyper_annotation: object = type_hints.get(
                hyper_param.name, hyper_param.annotation
            )
            if hyper_annotation is inspect.Signature.empty:
                raise AlgorithmValidationError(
                    "hyperparams must be type-annotated with a HyperParams subclass"
                )
            if not (
                inspect.isclass(hyper_annotation)
                and issubclass(hyper_annotation, HyperParams)
            ):
                raise AlgorithmValidationError(
                    "hyperparams must be a HyperParams subclass"
                )
            hyperparams_model = hyper_annotation  # type: ignore[assignment]

        ret_anno = sig.return_annotation  # pyright: ignore[reportAny]
        output_annotation: object = type_hints.get("return", ret_anno)
        if output_annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "output must be type-annotated with a BaseModel subclass"
            )
        if not (
            inspect.isclass(output_annotation)
            and issubclass(output_annotation, _PydanticBaseModel)
        ):
            raise AlgorithmValidationError(
                "algorithm output must be a BaseModel subclass"
            )

        # After validation, we know these are type[BaseModel] subclasses
        return (
            annotation,
            output_annotation,
            hyperparams_model,
        )  # type: ignore[return-value]


# Convenience instance for common imports
Algorithm = DefaultAlgorithmDecorator()
