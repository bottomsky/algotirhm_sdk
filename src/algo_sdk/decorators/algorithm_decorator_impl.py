"""Algorithm decorator for class-based algorithms."""

from __future__ import annotations

import inspect
from typing import Callable

from algo_sdk.core import (
    AlgorithmSpec,
    AlgorithmValidationError,
    BaseModel,
    ExecutionConfig,
    get_registry,
    AlgorithmLifecycleProtocol,
)
from algo_sdk.core.registry import AlgorithmRegistry


class DefaultAlgorithmDecorator:
    """Decorator used to register class-based algorithms."""

    _registry: AlgorithmRegistry

    def __init__(self, *, registry: AlgorithmRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    def __call__(
        self,
        *,
        name: str,
        version: str,
        description: str | None = None,
        execution: dict[str, object] | None = None,
    ) -> Callable[
        [
            type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]]
        ],
            type[
            AlgorithmLifecycleProtocol[BaseModel, BaseModel]
        ],
    ]:
        """Register a  class-based algorithm.

        Args:
            name: Algorithm name
            version: Algorithm version
            description: Optional description
            execution: Optional execution config dict

        Returns:
            A decorator that preserves the type of the decorated class
        """
        if not name or not version:
            raise AlgorithmValidationError(
                "name and version are required for registration")

        exec_config = self._build_execution_config(execution)

        def _decorator(
            target: type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]],
        ) -> type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]]:
            if inspect.isclass(target):
                spec = self._build_class_spec(
                    target,
                    name=name,
                    version=version,
                    description=description,
                    exec_config=exec_config,
                )
            else:
                raise AlgorithmValidationError(
                    "decorator target must be a callable or class")
            self._registry.register(spec)
            return target

        return _decorator

    def _build_execution_config(
            self, execution: dict[str, object] | None) -> ExecutionConfig:
        if not execution:
            return ExecutionConfig()

        allowed_keys = {"isolated_pool", "max_workers", "timeout_s", "gpu"}
        unknown = set(execution.keys()) - allowed_keys
        if unknown:
            raise AlgorithmValidationError(
                f"unknown execution keys: {', '.join(sorted(unknown))}")

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
            isolated_pool=isolated_pool,
            max_workers=max_workers,
            timeout_s=timeout_s,
            gpu=gpu,
        )

    def _build_class_spec(
        self,
        target_cls: type[AlgorithmLifecycleProtocol[BaseModel, BaseModel]],
        *,
        name: str,
        version: str,
        description: str | None,
        exec_config: ExecutionConfig,
    ) -> AlgorithmSpec[BaseModel, BaseModel]:
        run_method: object = getattr(target_cls, "run", None)
        if run_method is None or not callable(run_method):
            raise AlgorithmValidationError(
                "class-based algorithm must define a callable 'run' method")
        if getattr(run_method, "__isabstractmethod__", False):
            raise AlgorithmValidationError(
                "class-based algorithm must provide a concrete 'run' method")
        if inspect.isabstract(target_cls):
            raise AlgorithmValidationError(
                "class-based algorithm must not be abstract")

        input_model, output_model = self._extract_io(run_method)

        for hook_name in ("initialize", "after_run", "shutdown"):
            if not hasattr(target_cls, hook_name):
                raise AlgorithmValidationError(
                    f"hook '{hook_name}' must be implemented")
            hook = getattr(target_cls, hook_name)  # pyright: ignore[reportAny]
            if hook is not None and not callable(
                    hook):  # pyright: ignore[reportAny]
                raise AlgorithmValidationError(
                    f"hook '{hook_name}' must be callable or absent")

        return AlgorithmSpec(
            name=name,
            version=version,
            description=description,
            input_model=input_model,
            output_model=output_model,
            execution=exec_config,
            entrypoint=target_cls,
            is_class=True,
        )

    def _build_function_spec(
        self,
        func: Callable[..., object],
        *,
        name: str,
        version: str,
        description: str | None,
        exec_config: ExecutionConfig,
    ) -> AlgorithmSpec[BaseModel, BaseModel]:
        if not callable(func):
            raise AlgorithmValidationError("algorithm must be callable")
        input_model, output_model = self._extract_io(func, skip_first=False)
        return AlgorithmSpec(
            name=name,
            version=version,
            description=description,
            input_model=input_model,
            output_model=output_model,
            execution=exec_config,
            entrypoint=func,
            is_class=False,
        )

    def _extract_io(
        self,
        callable_obj: Callable[..., object],
        *,
        skip_first: bool = True,
    ) -> tuple[type[BaseModel], type[BaseModel]]:
        """Extract input/output models from callable signature.

        Args:
            run_method: The run method of the algorithm class

        Returns:
            Tuple of (input_model, output_model) types
        """
        sig = inspect.signature(callable_obj)
        params = list(sig.parameters.values())
        if skip_first and params:
            params = params[1:]

        if len(params) != 1:
            raise AlgorithmValidationError(
                "run method must accept exactly one argument (besides self)")

        param = params[0]
        annotation: object = param.annotation  # pyright: ignore[reportAny]
        if annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "input must be type-annotated with a BaseModel subclass")
        if not (inspect.isclass(annotation)
                and issubclass(annotation, BaseModel)):
            raise AlgorithmValidationError(
                "algorithm input must be a BaseModel subclass")

        ret_anno = sig.return_annotation  # pyright: ignore[reportAny]
        output_annotation: object = ret_anno
        if output_annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "output must be type-annotated with a BaseModel subclass")
        if not (inspect.isclass(output_annotation)
                and issubclass(output_annotation, BaseModel)):
            raise AlgorithmValidationError(
                "algorithm output must be a BaseModel subclass")

        # After validation, we know these are type[BaseModel] subclasses
        return (annotation, output_annotation)  # type: ignore[return-value]


# Convenience instance for common imports
Algorithm = DefaultAlgorithmDecorator()
