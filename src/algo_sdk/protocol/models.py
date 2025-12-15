from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel as _PydanticBaseModel
from pydantic import ConfigDict, Field, model_validator

CtxExtra = Dict[str, Any]
T = TypeVar("T")


class AlgorithmContext(_PydanticBaseModel):
    """Shared context carried with every algorithm invocation."""

    traceId: Optional[str] = None
    tenantId: Optional[str] = None
    userId: Optional[str] = None
    extra: CtxExtra = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AlgorithmRequest(_PydanticBaseModel, Generic[T]):
    """Standardized algorithm request envelope."""

    requestId: str = Field(min_length=1)
    datetime: datetime
    context: AlgorithmContext = Field(default_factory=AlgorithmContext)
    data: T

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _ensure_request_id(self) -> "AlgorithmRequest[T]":
        if not self.requestId or not self.requestId.strip():
            raise ValueError("requestId must be non-empty")
        return self


class AlgorithmResponse(_PydanticBaseModel, Generic[T]):
    """Standardized algorithm response envelope."""

    code: int
    message: str
    requestId: Optional[str] = None
    datetime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: Optional[AlgorithmContext] = None
    data: Optional[T] = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _ensure_message(self) -> "AlgorithmResponse[T]":
        if not self.message:
            raise ValueError("message must be provided")
        return self


def api_success(
    data: Optional[T] = None,
    *,
    request_id: Optional[str] = None,
    context: Optional[AlgorithmContext] = None,
    message: str = "success",
    code: int = 0,
) -> AlgorithmResponse[T]:
    """Convenience helper to wrap successful responses."""

    return AlgorithmResponse(
        code=code,
        message=message,
        requestId=request_id,
        context=context,
        data=data,
    )


def api_error(
    message: str,
    *,
    code: int = 500,
    request_id: Optional[str] = None,
    context: Optional[AlgorithmContext] = None,
    data: Optional[T] = None,
) -> AlgorithmResponse[T]:
    """Convenience helper to wrap error responses."""

    return AlgorithmResponse(
        code=code,
        message=message,
        requestId=request_id,
        context=context,
        data=data,
    )
