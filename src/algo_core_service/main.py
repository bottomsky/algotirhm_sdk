from __future__ import annotations

import os
import sys

from pathlib import Path

from dotenv import load_dotenv


def _env_file_path() -> Path:
    # .env.example is located at project root (same level as pyproject.toml)
    return Path(__file__).resolve().parents[2] / ".env.example"


def _load_env() -> None:
    env_path = _env_file_path()
    load_dotenv(env_path)


def _apply_pythonpath_from_env() -> None:
    """Apply PYTHONPATH env var to sys.path at runtime.

    Note: setting PYTHONPATH inside .env does not automatically affect sys.path
    for an already-started interpreter, so we add it here.
    """

    pythonpath = os.getenv("PYTHONPATH", "").strip()
    if not pythonpath:
        return

    project_root = Path(__file__).resolve().parents[2]
    for entry in pythonpath.split(os.pathsep):
        candidate = entry.strip()
        if not candidate:
            continue

        path = (
            (project_root / candidate).resolve()
            if not os.path.isabs(candidate)
            else Path(candidate).resolve()
        )
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def run_server() -> None:
    _load_env()
    _apply_pythonpath_from_env()

    from algo_sdk import run as run_http

    run_http(env_path=_env_file_path())


if __name__ == "__main__":
    run_server()
