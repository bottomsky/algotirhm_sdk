import importlib

import pytest


def test_algorithm_api_package_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("algo_sdk.algorithm_api")
