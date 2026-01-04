from __future__ import annotations

import logging
from collections.abc import Mapping

from ..protocol import ExcInfo, LoggingEventLoggerProtocol


class StandardLoggingEventLogger(LoggingEventLoggerProtocol):
    def log(
        self,
        level: int,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.log(level, message, *args, **kwargs)

    def debug(
        self,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.debug(message, *args, **kwargs)

    def info(
        self,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.info(message, *args, **kwargs)

    def warning(
        self,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.warning(message, *args, **kwargs)

    def error(
        self,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.error(message, *args, **kwargs)

    def exception(
        self,
        message: str,
        *args: object,
        logger: logging.Logger | None = None,
        extra: Mapping[str, object] | None = None,
        exc_info: ExcInfo = None,
        stacklevel: int = 3,
    ) -> None:
        target = logger or logging.getLogger()
        kwargs = self._build_kwargs(extra, exc_info, stacklevel)
        target.exception(message, *args, **kwargs)

    @staticmethod
    def _build_kwargs(
        extra: Mapping[str, object] | None,
        exc_info: ExcInfo,
        stacklevel: int,
    ) -> dict[str, object]:
        kwargs: dict[str, object] = {"stacklevel": stacklevel}
        if extra is not None:
            kwargs["extra"] = extra
        if exc_info is not None:
            kwargs["exc_info"] = exc_info
        return kwargs
