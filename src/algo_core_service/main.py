from __future__ import annotations

import os

from algo_sdk import create_app, http_server


def _load_algorithms() -> None:
    raw = os.getenv("ALGO_MODULES", "").strip()
    if raw:
        modules = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        modules = ["algo_core_service.algorithms"]
    http_server.load_algorithm_modules(modules)


_load_algorithms()
app = create_app()

__all__ = ["app"]
