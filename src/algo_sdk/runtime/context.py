from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

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


@dataclass(slots=True)
class ContextTokens:
    context: Token[AlgorithmContext | None]
    request_id: Token[str | None]
    trace_id: Token[str | None]


def set_execution_context(
    request_id: str | None,
    trace_id: str | None,
    context: AlgorithmContext | None,
) -> ContextTokens:
    return ContextTokens(
        context=_CURRENT_CONTEXT.set(context),
        request_id=_CURRENT_REQUEST_ID.set(request_id),
        trace_id=_CURRENT_TRACE_ID.set(trace_id),
    )


def reset_execution_context(tokens: ContextTokens) -> None:
    _CURRENT_CONTEXT.reset(tokens.context)
    _CURRENT_REQUEST_ID.reset(tokens.request_id)
    _CURRENT_TRACE_ID.reset(tokens.trace_id)


def get_current_context() -> AlgorithmContext | None:
    return _CURRENT_CONTEXT.get()


def get_current_request_id() -> str | None:
    return _CURRENT_REQUEST_ID.get()


def get_current_trace_id() -> str | None:
    return _CURRENT_TRACE_ID.get()


@contextmanager
def execution_context(
    *,
    request_id: str | None,
    trace_id: str | None,
    context: AlgorithmContext | None,
):
    tokens = set_execution_context(request_id, trace_id, context)
    try:
        yield
    finally:
        reset_execution_context(tokens)
