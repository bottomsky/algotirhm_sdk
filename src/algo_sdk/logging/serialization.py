"""Convert log values to JSON data without Python model representations."""

from __future__ import annotations

from pydantic_core import to_jsonable_python


def to_json_value(value: object) -> object:
    """Normalize models and temporal values without failing algorithm calls."""
    try:
        return to_jsonable_python(
            value,
            by_alias=True,
            inf_nan_mode="null",
            fallback=str,
        )
    except Exception as exc:
        # A broken custom serializer must not break a successful algorithm.
        return {
            "serialization_error": str(exc),
            "value_type": type(value).__name__,
        }
