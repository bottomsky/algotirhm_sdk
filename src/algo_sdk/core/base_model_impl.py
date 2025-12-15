from __future__ import annotations

from pydantic import BaseModel as _PydanticBaseModel
from pydantic import ConfigDict


class BaseModel(_PydanticBaseModel):
    """Base model used across the SDK with strict field handling."""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_min_length=1,
    )
