from __future__ import annotations

from pydantic import BaseModel as _PydanticBaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class BaseModel(_PydanticBaseModel):
    """Base model used across the SDK with strict field handling."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_min_length=1,
    )
