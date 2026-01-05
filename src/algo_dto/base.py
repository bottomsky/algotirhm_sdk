"""Business-domain models used as algorithm inputs/outputs.

These models are transported via algo_sdk.protocol AlgorithmRequest/
AlgorithmResponse `data` fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Generic, Self, TypeVar

import numpy as np
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
)
from pydantic.alias_generators import to_camel


class CamelBaseModel(BaseModel):
    """Base model that converts snake_case fields to camelCase JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


TVal = TypeVar("TVal", float, int)


class _VectorBase(RootModel[list[TVal]], Generic[TVal]):
    """Fixed-length vector that serializes as a JSON array."""

    model_config = ConfigDict(frozen=True)
    size: ClassVar[int]

    @field_validator("root")
    @classmethod
    def _validate_length(cls, value: list[TVal]) -> list[TVal]:
        if len(value) != cls.size:
            raise ValueError(f"expected {cls.size} elements, got {len(value)}")
        return value

    @classmethod
    def from_values(cls, *values: TVal) -> Self:
        """
        从可变参数创建向量实例
        参数:
          - values: 向量的元素序列（长度必须等于 cls.size）
        返回:
          - Self: 当前向量类型的实例
        异常:
          - ValueError: 当元素数量与 cls.size 不一致
          - pydantic.ValidationError: 当元素类型不符合模型约束
        """
        return cls.model_validate(list(values))

    @classmethod
    def from_np_array(cls, array: object) -> Self:
        """
        从 numpy 数组或可转换为 numpy 数组的对象创建向量实例
        参数:
          - array: numpy.ndarray 或任何可被 numpy.asarray 转换的序列/数组对象
        返回:
          - Self: 当前向量类型的实例
        异常:
          - ValueError: 当数组无法转换或元素数量与 cls.size 不一致
          - pydantic.ValidationError: 当元素类型不符合模型约束
        """
        arr = np.asarray(array).reshape(-1)
        if arr.size != cls.size:
            raise ValueError(f"expected {cls.size} elements, got {arr.size}")
        return cls.model_validate(arr.tolist())

    @classmethod
    def from_an_array(cls, array: object) -> Self:
        """
        从数组创建向量实例（from_np_array 的兼容别名）
        参数:
          - array: numpy.ndarray 或任何可被 numpy.asarray 转换的序列/数组对象
        返回:
          - Self: 当前向量类型的实例
        异常:
          - ValueError: 当数组无法转换或元素数量与 cls.size 不一致
          - pydantic.ValidationError: 当元素类型不符合模型约束
        """
        return cls.from_np_array(array)

    def to_list(self) -> list[TVal]:
        return list(self.root)

    def to_np_array(
        self, *, dtype: object | None = None, copy: bool = True
    ) -> np.ndarray:
        """
        导出为 numpy.ndarray
        参数:
          - dtype: 传递给 numpy.array 的 dtype（可选）
          - copy: 是否复制数据（默认 True）
        返回:
          - numpy.ndarray: 形状为 (size,) 的一维数组
        异常:
          - TypeError: dtype 参数不合法
          - ValueError: 当 numpy 转换失败
        """
        return np.array(self.root, dtype=dtype, copy=copy)

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


class VVLHRV(Vector6):
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


class MessageResponseBase(CamelBaseModel):
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
    "VVLHRV",
    "SimTime",
    "CamelBaseModel",
    "MessageResponse",
]


class TimeRange:
    start_time: SimTime
    end_time: SimTime


class Timestamp:
    sim_time: SimTime = Field(
        validation_alias=AliasChoices("simTime", "startTime"),
        serialization_alias="simTime",
    )
