from __future__ import annotations

from typing import ClassVar, Self, TypeVar, Generic

from pydantic import BaseModel, ConfigDict, RootModel, field_validator

from datetime import datetime


TVal = TypeVar("TVal", float, int)


class _VectorBase(RootModel[list[TVal]], Generic[TVal]):
    """Fixed-length vector that serializes as a JSON array."""

    model_config = ConfigDict(frozen=True)
    size: ClassVar[int]

    @field_validator("root")
    @classmethod
    def _validate_length(cls, value: list[TVal]) -> list[TVal]:
        if len(value) != cls.size:
            raise ValueError(
                f"expected {cls.size} elements, got {len(value)}"
            )
        return value

    @classmethod
    def from_values(cls, *values: TVal) -> Self:
        return cls.model_validate(list(values))

    def to_list(self) -> list[TVal]:
        return list(self.root)

    def to_tuple(self) -> tuple[TVal, ...]:
        return tuple(self.root)

    def __iter__(self):
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> TVal:
        return self.root[index]


class Vector2(_VectorBase[float]):
    size = 2


class Vector3(_VectorBase[float]):
    size = 3


class Vector4(_VectorBase[float]):
    size = 4


class Vector6(_VectorBase[float]):
    size = 6


class Vector2i(_VectorBase[int]):
    size = 2


class Vector3i(_VectorBase[int]):
    size = 3


class Vector4i(_VectorBase[int]):
    size = 4


class Vector6i(_VectorBase[int]):
    size = 6


class VVLHRv(Vector6):
    """VVLH coordinates and rates [rx, ry, rz, vx, vy, vz]."""

    def relative_position_vector(self) -> Vector3:
        """Returns the relative position as a Vector3."""
        return Vector3.from_values(*self.root[:3])

    def relative_position_array(self) -> list[float]:
        """Returns the relative position as a list of 3 floats."""
        return list(self.root[:3])

    def velocity_vector(self) -> Vector3:
        """Returns the velocity as a Vector3."""
        return Vector3.from_values(*self.root[3:])

    def velocity_array(self) -> list[float]:
        """Returns the velocity as a list of 3 floats."""
        return list(self.root[3:])

    def update(
        self,
        pos: Vector3 | list[float] | None = None,
        vel: Vector3 | list[float] | None = None,
    ) -> Self:
        """Returns a new VVLHRv with updated position and/or velocity."""
        new_pos = pos if pos is not None else self.relative_position_array()
        new_vel = vel if vel is not None else self.velocity_array()
        return self.create(pos=new_pos, vel=new_vel)

    def update_rv(self, rv: Vector6 | list[float]) -> Self:
        """Returns a new instance from a Vector6 or 6-element array."""
        data = rv.root if isinstance(rv, Vector6) else list(rv)
        return self.model_validate(data)

    @classmethod
    def create(
        cls, pos: Vector3 | list[float], vel: Vector3 | list[float]
    ) -> Self:
        """Creates a VVLHRv from position and velocity vectors or lists."""
        p_list = pos.root if isinstance(pos, Vector3) else list(pos)
        v_list = vel.root if isinstance(vel, Vector3) else list(vel)
        return cls.from_values(*(p_list + v_list))


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
    "Vector2i",
    "Vector3i",
    "Vector4i",
    "Vector6i",
    "VVLHRv",
    "SimTime",
    "MessageResponse"
]