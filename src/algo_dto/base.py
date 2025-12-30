from __future__ import annotations

from typing import ClassVar, Self, TypeVar, Generic

from pydantic import BaseModel, ConfigDict, RootModel, field_validator

from datetime import datetime


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


class SimTime(RootModel[list[int]]):
    """Time representation as a fixed-length array
    [year, month, day, hour, minute, second]."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def _validate_length(cls, value: list[int]) -> list[int]:
        if len(value) != 6:
            raise ValueError(f"expected 6 elements, got {len(value)}")
        return value

    def to_datetime(self) -> datetime:
        """Convert to Python datetime object."""
        return datetime(*self.root)

    @classmethod
    def from_datetime(cls, dt: datetime) -> SimTime:
        """Create SimTime from Python datetime object from year to second."""
        return cls([dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second])

    @property
    def year(self) -> int:
        return self.root[0]

    @property
    def month(self) -> int:
        return self.root[1]

    @property
    def day(self) -> int:
        return self.root[2]

    @property
    def hour(self) -> int:
        return self.root[3]

    @property
    def minute(self) -> int:
        return self.root[4]

    @property
    def second(self) -> int:
        return self.root[5]

    def __getitem__(self, index: int) -> int:
        return self.root[index]

    def __iter__(self):
        return iter(self.root)

    def __len__(self) -> int:
        return 6


TData = TypeVar("TData")


class MessageResponseBase(BaseModel):
    code: int
    message: str


class MessageResponse(MessageResponseBase, Generic[TData]):
    data: TData

    @classmethod
    def create(
        cls, data: TData, code: int = 0, message: str = "success"
    ) -> Self:
        return cls(code=code, data=data, message=message)

    @classmethod
    def success(
        cls, data: TData, code: int = 0, message: str = "success"
    ) -> Self:
        return cls(code=code, data=data, message=message)

    @classmethod
    def failure(
        cls, data: TData, code: int = 1, message: str = "failure"
    ) -> Self:
        return cls(code=code, data=data, message=message)


__all__ = [
    "Vector2",
    "Vector3",
    "Vector4",
    "Vector6",
    "SimTime",
    "MessageResponse"
]