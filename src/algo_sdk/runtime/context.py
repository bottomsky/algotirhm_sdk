from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ..protocol.models import AlgorithmContext

_CURRENT_CONTEXT: ContextVar[AlgorithmContext | None] = ContextVar(
    "algo_context",
    default=None,
)
_CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar(
    "algo_request_id",
    default=None,
)
_CURRENT_TRACE_ID: ContextVar[str | None] = ContextVar(
    "algo_trace_id",
    default=None,
)
_CURRENT_REQUEST_DATETIME: ContextVar[datetime | None] = ContextVar(
    "algo_request_datetime",
    default=None,
)
_CURRENT_RESPONSE_META: ContextVar["ResponseMeta | None"] = ContextVar(
    "algo_response_meta",
    default=None,
)


@dataclass(slots=True)
class ResponseMeta:
    code: int | None = None
    message: str | None = None
    context: AlgorithmContext | None = None


@dataclass(slots=True)
class ContextTokens:
    context: Token[AlgorithmContext | None]
    request_id: Token[str | None]
    trace_id: Token[str | None]
    request_datetime: Token[datetime | None]
    response_meta: Token[ResponseMeta | None]


def set_execution_context(
    request_id: str | None,
    trace_id: str | None,
    request_datetime: datetime | None,
    context: AlgorithmContext | None,
) -> ContextTokens:
    return ContextTokens(
        context=_CURRENT_CONTEXT.set(context),
        request_id=_CURRENT_REQUEST_ID.set(request_id),
        trace_id=_CURRENT_TRACE_ID.set(trace_id),
        request_datetime=_CURRENT_REQUEST_DATETIME.set(request_datetime),
        response_meta=_CURRENT_RESPONSE_META.set(None),
    )


def reset_execution_context(tokens: ContextTokens) -> None:
    _CURRENT_CONTEXT.reset(tokens.context)
    _CURRENT_REQUEST_ID.reset(tokens.request_id)
    _CURRENT_TRACE_ID.reset(tokens.trace_id)
    _CURRENT_REQUEST_DATETIME.reset(tokens.request_datetime)
    _CURRENT_RESPONSE_META.reset(tokens.response_meta)


def get_current_context() -> AlgorithmContext | None:
    return _CURRENT_CONTEXT.get()


def get_current_request_id() -> str | None:
    return _CURRENT_REQUEST_ID.get()


def get_current_trace_id() -> str | None:
    return _CURRENT_TRACE_ID.get()


def get_current_request_datetime() -> datetime | None:
    return _CURRENT_REQUEST_DATETIME.get()


def _ensure_response_meta() -> ResponseMeta:
    meta = _CURRENT_RESPONSE_META.get()
    if meta is None:
        meta = ResponseMeta()
        _CURRENT_RESPONSE_META.set(meta)
    return meta


def set_response_code(code: int) -> None:
    meta = _ensure_response_meta()
    meta.code = code


def set_response_message(message: str) -> None:
    meta = _ensure_response_meta()
    meta.message = message


def set_response_context(
    context: AlgorithmContext | Mapping[str, Any] | None,
) -> None:
    meta = _ensure_response_meta()
    if context is None:
        meta.context = None
        return
    if isinstance(context, AlgorithmContext):
        meta.context = context
        return
    meta.context = AlgorithmContext.model_validate(context)


def get_response_meta() -> ResponseMeta | None:
    return _CURRENT_RESPONSE_META.get()


@contextmanager
def execution_context(
    *,
    request_id: str | None,
    trace_id: str | None,
    request_datetime: datetime | None = None,
    context: AlgorithmContext | None,
):
    tokens = set_execution_context(
        request_id, trace_id, request_datetime, context
    )
    try:
        yield
    finally:
        reset_execution_context(tokens)
