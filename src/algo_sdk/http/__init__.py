from .impl.lifecycle_hooks import AlgorithmHttpServiceHook
from .impl.service import AlgorithmHttpService, ObservationHooks

__all__ = [
    "AlgorithmHttpService",
    "AlgorithmHttpServiceHook",
    "ObservationHooks",
    "create_app",
    "run",
]


def create_app(*args, **kwargs):
    from .impl.server import create_app as _create_app
    return _create_app(*args, **kwargs)


def run(*args, **kwargs):
    from .impl.server import run as _run
    return _run(*args, **kwargs)
