from __future__ import annotations

from pathlib import Path


def test_sgp_dotnet_default_dll_dir_points_to_repo_lib(
    monkeypatch,
) -> None:
    """
    校验 SgpDotnetTestAlgorithm 默认 DLL 目录指向仓库 lib
    参数:
      - monkeypatch: pytest fixture，用于隔离环境变量
    返回:
      - None
    异常:
      - AssertionError: 当默认路径不符合预期时抛出
    """
    monkeypatch.delenv("SGP_DOTNET_DLL_DIR", raising=False)

    from algo_core_service.algorithms.sgp_dotnet_test import _read_sgp_dll_dir

    dll_dir = Path(_read_sgp_dll_dir())
    assert dll_dir.name == "lib"
    assert (dll_dir / "SGP.NET.dll").is_file()
