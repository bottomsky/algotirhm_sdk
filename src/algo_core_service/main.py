from __future__ import annotations

from pathlib import Path


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def run_server() -> None:
    from algo_sdk import run as run_http

    run_http(env_path=ENV_FILE)


if __name__ == "__main__":
    run_server()
