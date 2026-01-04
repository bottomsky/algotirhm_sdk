from __future__ import annotations

import os

from pathlib import Path

from dotenv import load_dotenv

from algo_sdk import create_app, http_server


def _load_algorithms() -> None:
    raw = os.getenv("ALGO_MODULES", "").strip()
    if raw:
        modules = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        modules = ["algo_core_service.algorithms"]
    http_server.load_algorithm_modules(modules)


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)


_load_env()
_load_algorithms()
app = create_app()

__all__ = ["app"]
