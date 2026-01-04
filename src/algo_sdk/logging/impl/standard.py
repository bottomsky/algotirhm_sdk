from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from ..protocol import LoggingConfiguratorProtocol
from ..settings import LoggingSettings

_BUILTIN_LOG_RECORD_ATTRS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.threadName,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _BUILTIN_LOG_RECORD_ATTRS
        }
        if extras:
            payload.update(extras)
        return json.dumps(payload, ensure_ascii=True, default=str)


class PayloadLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return (
            hasattr(record, "input_preview")
            or hasattr(record, "output_preview")
        )


class StandardLoggingConfigurator(LoggingConfiguratorProtocol):
    def __init__(self, settings: LoggingSettings) -> None:
        self._settings = settings

    def configure(self) -> None:
        logger = logging.getLogger()
        marker = "_algo_sdk_logging_configured"
        if getattr(logger, marker, False):
            return
        logger.setLevel(self._settings.level)
        formatter = JsonFormatter()
        for handler in self._build_handlers(formatter):
            logger.addHandler(handler)
        setattr(logger, marker, True)

    def _build_handlers(
        self, formatter: logging.Formatter
    ) -> list[logging.Handler]:
        handlers: list[logging.Handler] = []
        if self._settings.console_enabled:
            console = logging.StreamHandler()
            console.setLevel(self._settings.level)
            console.setFormatter(formatter)
            handlers.append(console)

        if self._settings.error_dir:
            handlers.append(
                self._build_file_handler(
                    self._settings.error_dir,
                    "error.log",
                    level=logging.ERROR,
                    formatter=formatter,
                )
            )

        if self._settings.payload_dir:
            payload_handler = self._build_file_handler(
                self._settings.payload_dir,
                "payload.log",
                level=self._settings.level,
                formatter=formatter,
            )
            payload_handler.addFilter(PayloadLogFilter())
            handlers.append(payload_handler)

        if self._settings.general_enabled and self._settings.general_dir:
            handlers.append(
                self._build_file_handler(
                    self._settings.general_dir,
                    "service.log",
                    level=self._settings.level,
                    formatter=formatter,
                )
            )

        return handlers

    def _build_file_handler(
        self,
        directory: str,
        filename: str,
        *,
        level: int,
        formatter: logging.Formatter,
    ) -> logging.Handler:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, filename)
        handler = TimedRotatingFileHandler(
            path,
            when=self._settings.rotate_when,
            backupCount=self._settings.backup_count,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
