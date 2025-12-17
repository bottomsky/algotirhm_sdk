from __future__ import annotations

import inspect
import inspect
from typing import Any, Callable, Protocol, TypeVar, cast, overload

from algo_sdk.core import AlgorithmSpec, AlgorithmValidationError, BaseModel, ExecutionConfig, get_registry
from algo_sdk.core.lifecycle import AlgorithmLifecycle
from algo_sdk.core.registry import AlgorithmRegistry

Req = TypeVar("Req", bound=BaseModel)
Resp = TypeVar("Resp", bound=BaseModel)
FnReq = TypeVar("FnReq", bound=BaseModel)
FnResp = TypeVar("FnResp", bound=BaseModel)
ClsReq = TypeVar("ClsReq", bound=BaseModel)
ClsResp = TypeVar("ClsResp", bound=BaseModel)


class _AlgorithmClassProto(Protocol[ClsReq, ClsResp]):
    """Structural protocol for class-based algorithms."""

    def run(self, req: ClsReq) -> ClsResp: ...

    def initialize(self) -> None: ...

    def after_run(self) -> None: ...

    def shutdown(self) -> None: ...


class DefaultAlgorithmDecorator:
    """Decorator used to register algorithms (function or class-based)."""

    def __init__(self, *, registry: AlgorithmRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    @overload
    def __call__(
        self,
        *,
        name: str,
        version: str,
        description: str | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Callable[[Callable[[FnReq], FnResp]], Callable[[FnReq], FnResp]]:
        ...

    @overload
    def __call__(
        self,
        *,
        name: str,
        version: str,
        description: str | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Callable[
        [type[_AlgorithmClassProto[ClsReq, ClsResp]]],
        type[_AlgorithmClassProto[ClsReq, ClsResp]],
    ]:
        ...

    def __call__(
        self,
        *,
        name: str,
        version: str,
        description: str | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Callable[[object], object]:
        if not name or not version:
            raise AlgorithmValidationError(
                "name and version are required for registration")

        exec_config = self._build_execution_config(execution)

        def _decorator(
            target: Callable[[BaseModel], BaseModel] | type[Any]
        ) -> object:
            typed_target = cast(
                Callable[[Req], Resp]
                | type[_AlgorithmClassProto[Req, Resp]], target)
            spec = self._build_spec(typed_target, name, version, description,
                                    exec_config)
            self._registry.register(spec)
            return target

        return _decorator

    def _build_execution_config(
            self, execution: dict[str, Any] | None) -> ExecutionConfig:
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

    def _build_spec(
        self,
        target: Callable[[Req], Resp]
        | type[_AlgorithmClassProto[Req, Resp]],
        name: str,
        version: str,
        description: str | None,
        exec_config: ExecutionConfig,
    ) -> AlgorithmSpec[Req, Resp]:
        if inspect.isclass(target):
            cls_target = cast(type[_AlgorithmClassProto[Req, Resp]], target)
            return self._build_class_spec(cls_target,
                                          name=name,
                                          version=version,
                                          description=description,
                                          exec_config=exec_config)

        if not callable(target):
            raise AlgorithmValidationError(
                "decorated target must be a callable or class")

        func_target = cast(Callable[[Req], Resp], target)
        input_model, output_model = self._extract_io(func_target,
                                                     skip_first=False)
        return AlgorithmSpec(
            name=name,
            version=version,
            description=description,
            input_model=input_model,
            output_model=output_model,
            execution=exec_config,
            entrypoint=func_target,
            is_class=False,
        )

    def _build_class_spec(
        self,
        target_cls: type[_AlgorithmClassProto[Req, Resp]],
        *,
        name: str,
        version: str,
        description: str | None,
        exec_config: ExecutionConfig,
    ) -> AlgorithmSpec[Req, Resp]:
        run_method = getattr(target_cls, "run", None)
        if run_method is None or not callable(run_method):
            raise AlgorithmValidationError(
                "class-based algorithm must define a callable 'run' method")
        if getattr(run_method, "__isabstractmethod__", False):
            raise AlgorithmValidationError(
                "class-based algorithm must provide a concrete 'run' method")
        if inspect.isabstract(target_cls):
            raise AlgorithmValidationError(
                "class-based algorithm must not be abstract")

        input_model, output_model = self._extract_io(run_method,
                                                     skip_first=True)

        for hook_name in ("initialize", "after_run", "shutdown"):
            if not hasattr(target_cls, hook_name):
                setattr(target_cls, hook_name,
                        lambda self: None)  # type: ignore[misc]
                continue
            hook = getattr(target_cls, hook_name)
            if hook is not None and not callable(hook):
                raise AlgorithmValidationError(
                    f"class-based algorithm hook '{hook_name}' must be callable or absent")

        return AlgorithmSpec(
            name=name,
            version=version,
            description=description,
            input_model=input_model,
            output_model=output_model,
            execution=exec_config,
            entrypoint=cast(type[AlgorithmLifecycle[Req, Resp]], target_cls),
            is_class=True,
        )

    def _extract_io(self, fn: Callable[..., Any], *,
                    skip_first: bool) -> tuple[type[Req], type[Resp]]:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if skip_first and params:
            params = params[1:]

        if len(params) != 1:
            raise AlgorithmValidationError(
                "algorithm entrypoint must accept exactly one argument")

        param = params[0]
        if param.annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "algorithm input must be type-annotated with a BaseModel subclass"
            )
        if not inspect.isclass(param.annotation) or not issubclass(
                param.annotation, BaseModel):
            raise AlgorithmValidationError(
                "algorithm input must be a BaseModel subclass")

        output_annotation = sig.return_annotation
        if output_annotation is inspect.Signature.empty:
            raise AlgorithmValidationError(
                "algorithm output must be type-annotated with a BaseModel subclass"
            )
        if not inspect.isclass(output_annotation) or not issubclass(
                output_annotation, BaseModel):
            raise AlgorithmValidationError(
                "algorithm output must be a BaseModel subclass")

        return param.annotation, output_annotation


# Default export aligning with design doc usage.
Algorithm = DefaultAlgorithmDecorator()
