from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from algo_dto.base import VVLHRV
from algo_dto.dto import (
    PredictionRequest,
    PredictionResult,
    PredictionResultItem,
)
from algo_sdk import Algorithm, BaseAlgorithm
from algo_sdk.core import AlgorithmType, LoggingConfig
from algo_sdk.runtime import (
    set_response_code,
    set_response_context,
    set_response_message,
)


def _get_repo_root() -> Path:
    """
    获取仓库根目录路径
    参数:
      - 无
    返回:
      - Path: 仓库根目录路径
    异常:
      - 无；若未找到 pyproject.toml 则回退到路径层级推导
    """
    start = Path(__file__).resolve()
    for parent in start.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return start.parents[3]


def _read_sgp_dll_dir() -> str:
    """
    读取 SGP.NET.dll 所在目录
    参数:
      - 无
    返回:
      - str: 动态库目录路径
    异常:
      - 无；若环境变量不存在则返回默认 lib 目录
    """
    default_dir = str(_get_repo_root() / "lib")
    return os.getenv("SGP_DOTNET_DLL_DIR", default_dir)


def _read_tle_url() -> str:
    """
    读取远程 TLE 数据源 URL
    参数:
      - 无
    返回:
      - str: TLE URL
    异常:
      - 无；若环境变量不存在则返回默认 Celestrak 地址
    """
    return os.getenv(
        "SGP_TLE_URL",
        "https://celestrak.com/NORAD/elements/visual.txt",
    )


def _read_ground_station() -> tuple[float, float, float]:
    """
    读取地面站经纬高（纬度、经度、海拔 km）
    参数:
      - 无
    返回:
      - tuple[float, float, float]: (lat_deg, lon_deg, alt_km)
    异常:
      - ValueError: 环境变量存在但无法转换为 float
    """
    lat = float(os.getenv("SGP_GS_LAT", "30.229777"))
    lon = float(os.getenv("SGP_GS_LON", "-81.617525"))
    alt_km = float(os.getenv("SGP_GS_ALT_KM", "0"))
    return lat, lon, alt_km


def _ensure_sgp_assembly_loaded(dll_dir: str) -> None:
    """
    通过 pythonnet 加载 SGP.NET 程序集
    参数:
      - dll_dir: str，包含 SGP.NET.dll 的目录
    返回:
      - None
    异常:
      - RuntimeError: 当 pythonnet/clr 不可用或程序集加载失败时抛出
    """
    try:
        import pythonnet  # type: ignore[import-not-found]

        try:
            pythonnet.load("coreclr")
        except Exception:
            pass
    except Exception:
        pass

    try:
        import clr  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "pythonnet/clr is not available; ensure pythonnet is installed "
            "and .NET runtime is available"
        ) from exc

    dll_path_obj = Path(dll_dir)
    if not dll_path_obj.is_dir():
        raise RuntimeError(
            f"SGP.NET dll directory not found: {dll_dir}. "
            "Set SGP_DOTNET_DLL_DIR to the directory containing SGP.NET.dll."
        )

    if dll_dir not in sys.path:
        sys.path.append(dll_dir)

    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(dll_dir)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Failed to add dll directory: {dll_dir}. "
                "Set SGP_DOTNET_DLL_DIR to the directory containing "
                "SGP.NET.dll."
            ) from exc

    try:
        clr.AddReference("SGP.NET")
        return
    except Exception:
        pass

    dll_path = str(dll_path_obj / "SGP.NET.dll")
    try:
        clr.AddReference(dll_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load SGP.NET assembly from {dll_dir}"
        ) from exc


def _try_get_int(value: Any, default: int = 0) -> int:
    """
    将任意值尽力转换为 int
    参数:
      - value: Any，待转换值
      - default: int，转换失败时的默认值
    返回:
      - int: 转换结果
    异常:
      - 无；内部吞掉转换异常
    """
    try:
        return int(value)
    except Exception:
        return default


@Algorithm(
    name="SgpDotnetTest",
    version="v1",
    description="SGP.NET (.NET 8) DLL invocation test algorithm.",
    algorithm_type=AlgorithmType.PREDICTION,
    created_time="2026-01-13",
    author="algo-team",
    category="Diagnostics",
    application_scenarios="demo",
    extra={"owner": "algo-core-service"},
    logging=LoggingConfig(enabled=True, log_input=True, log_output=True),
)
class SgpDotnetTestAlgorithm(
    BaseAlgorithm[PredictionRequest, PredictionResult]
):
    def run(self, req: PredictionRequest) -> PredictionResult:
        """
        测试通过 pythonnet 调用 SGP.NET.dll，并执行一次外推/观测流程
        参数:
          - req: PredictionRequest，请求数据（本测试主要复用 sim_time/duration_s）
        返回:
          - PredictionResult: 单条结果，用于承载观测角度与卫星信息摘要
        异常:
          - RuntimeError: 当程序集或 .NET 类型加载失败时抛出
        """
        dll_dir = _read_sgp_dll_dir()
        _ensure_sgp_assembly_loaded(dll_dir)

        from SGPdotNET.CoordinateSystem import (  # type: ignore[import-not-found]
            GeodeticCoordinate,
        )
        from SGPdotNET.Observation import (  # type: ignore[import-not-found]
            GroundStation,
            Satellite,
        )
        from SGPdotNET.TLE import (
            RemoteTleProvider,  # type: ignore[import-not-found]
        )
        from SGPdotNET.Util import Angle  # type: ignore[import-not-found]
        from System import DateTime, Uri  # type: ignore[import-not-found]

        tle_url = _read_tle_url()
        provider = RemoteTleProvider(True, Uri(tle_url))
        tles = provider.GetTles()

        first_kv: Any | None = None
        for kv in tles:
            first_kv = kv
            break

        if first_kv is None:
            raise RuntimeError("SGP.NET returned empty TLE set")

        sat = Satellite(first_kv.Value)
        pos = sat.Predict()

        lat, lon, alt_km = _read_ground_station()

        lat_angle = Angle.FromDegrees(float(lat))
        lon_angle = Angle.FromDegrees(float(lon))
        gs = GroundStation(GeodeticCoordinate(lat_angle, lon_angle, alt_km))

        min_angle = Angle.op_Implicit(10)
        obs = gs.Observe(sat, DateTime.UtcNow)

        elevation_deg = float(obs.Elevation.Degrees)
        azimuth_deg = float(obs.Azimuth.Degrees)
        sat_id = _try_get_int(getattr(sat, "NoradNumber", None), default=0)
        if sat_id == 0:
            sat_id = _try_get_int(getattr(first_kv, "Key", None), default=0)

        set_response_code(2001)
        set_response_message("sgp dotnet ok")
        set_response_context(
            {
                "traceId": "trace-sgp-dotnet-test",
                "extra": {
                    "dllDir": dll_dir,
                    "tleUrl": tle_url,
                    "satelliteName": str(getattr(sat, "Name", "")),
                    "predictTimeUtc": str(getattr(pos, "Time", "")),
                    "elevationDeg": elevation_deg,
                    "azimuthDeg": azimuth_deg,
                    "minAngleDeg": float(min_angle.Degrees),
                    "groundStation": {
                        "latDeg": lat,
                        "lonDeg": lon,
                        "altKm": alt_km,
                    },
                },
            }
        )

        item = PredictionResultItem(
            sat_id=sat_id,
            min_distance=elevation_deg,
            relative_state_vvlh=VVLHRV.from_values(
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            ),
            score=1.0 if elevation_deg > 0 else 0.0,
            t_nearest_time=req.sim_time,
        )

        return PredictionResult(root=[item])
