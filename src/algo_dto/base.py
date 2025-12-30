from __future__ import annotations

from typing import ClassVar, Self

from pydantic import ConfigDict, RootModel, field_validator


class _VectorBase(RootModel[list[float]]):
    """Fixed-length vector that serializes as a JSON array."""

    model_config = ConfigDict(frozen=True)
    size: ClassVar[int]

    @field_validator("root")
    @classmethod
    def _validate_length(cls, value: list[float]) -> list[float]:
        if len(value) != cls.size:
            raise ValueError(
                f"expected {cls.size} elements, got {len(value)}"
            )
        return value

    @classmethod
    def from_values(cls, *values: float) -> Self:
        return cls.model_validate(list(values))

    def to_list(self) -> list[float]:
        return list(self.root)

    def to_tuple(self) -> tuple[float, ...]:
        return tuple(self.root)

    def __iter__(self):
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> float:
        return self.root[index]


class Vector2(_VectorBase):
    size = 2


class Vector3(_VectorBase):
    size = 3


class Vector4(_VectorBase):
    size = 4


class Vector6(_VectorBase):
    size = 6


__all__ = ["Vector2", "Vector3", "Vector4", "Vector6"]
