from __future__ import annotations

from .factory import build_event_logger
from .protocol import LoggingEventLoggerProtocol

_EVENT_LOGGER = build_event_logger()


def get_event_logger() -> LoggingEventLoggerProtocol:
    return _EVENT_LOGGER
