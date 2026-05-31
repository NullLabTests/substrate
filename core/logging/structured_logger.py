"""Structured JSON logger with stdout and file output."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class LogLevel:
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    _LEVEL_MAP = {
        DEBUG: logging.DEBUG,
        INFO: logging.INFO,
        WARNING: logging.WARNING,
        ERROR: logging.ERROR,
        CRITICAL: logging.CRITICAL,
    }


class StructuredLogger:
    """Structured JSON logger with correlation ID support.

    Logs to both stdout (JSON lines) and a rotating file.
    Each log entry includes timestamp, severity, module, correlation_id,
    message, and an optional payload dict.
    """

    def __init__(
        self,
        name: str = "substrate",
        level: str = LogLevel.INFO,
        file_path: str | Path | None = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        self._name = name
        self._level = level
        self._logger = logging.getLogger(name)
        self._logger.setLevel(LogLevel._LEVEL_MAP.get(level, logging.INFO))
        self._logger.handlers.clear()
        self._logger.propagate = False

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(_JSONFormatter(name=name))
        self._logger.addHandler(stdout_handler)

        if file_path:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(path), maxBytes=max_bytes, backupCount=backup_count
            )
            file_handler.setFormatter(_JSONFormatter(name=name))
            self._logger.addHandler(file_handler)

    async def initialize(self) -> None:
        """Prepare the logger."""

    async def shutdown(self) -> None:
        """Flush and close all handlers."""
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)

    async def save_state(self) -> dict[str, Any]:
        return {"name": self._name, "level": self._level}

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        if state:
            self._level = state.get("level", self._level)

    def debug(
        self,
        message: str,
        module: str = "",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> None:
        self._log(LogLevel.DEBUG, message, module, correlation_id, payload)

    def info(
        self,
        message: str,
        module: str = "",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> None:
        self._log(LogLevel.INFO, message, module, correlation_id, payload)

    def warning(
        self,
        message: str,
        module: str = "",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> None:
        self._log(LogLevel.WARNING, message, module, correlation_id, payload)

    def error(
        self,
        message: str,
        module: str = "",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> None:
        self._log(LogLevel.ERROR, message, module, correlation_id, payload)

    def critical(
        self,
        message: str,
        module: str = "",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> None:
        self._log(LogLevel.CRITICAL, message, module, correlation_id, payload)

    def _log(
        self,
        level: str,
        message: str,
        module: str,
        correlation_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        extra = {
            "_module": module or self._name,
            "correlation_id": correlation_id,
            "payload": payload,
        }
        self._logger.log(
            LogLevel._LEVEL_MAP.get(level, logging.INFO),
            message,
            extra=extra,
        )


class _JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname.lower(),
            "module": getattr(record, "_module", self._name),
            "correlation_id": getattr(record, "correlation_id", None),
            "message": record.getMessage(),
            "payload": getattr(record, "payload", {}),
        }
        return json.dumps(entry, default=str)
