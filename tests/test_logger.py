"""Tests for StructuredLogger."""

from __future__ import annotations

import json
import io
import logging
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.logging.structured_logger import StructuredLogger


class TestStructuredLogger:
    async def test_log_levels(self) -> None:
        log = StructuredLogger("test_log_levels", level="debug")
        await log.initialize()
        log.debug("debug msg", module="test")
        log.info("info msg", module="test")
        log.warning("warn msg", module="test")
        log.error("err msg", module="test")
        log.critical("crit msg", module="test")
        await log.shutdown()

    async def test_log_to_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name
        log = StructuredLogger("test_file", level="info", file_path=log_path)
        await log.initialize()
        log.info("file log test", module="test", user_id=42)
        await log.shutdown()
        content = Path(log_path).read_text()
        assert "file log test" in content
        assert "user_id" in content
        Path(log_path).unlink()

    async def test_save_and_load_state(self) -> None:
        log = StructuredLogger("test_state", level="debug")
        await log.initialize()
        state = await log.save_state()
        assert state["name"] == "test_state"
        assert state["level"] == "debug"
        new_log = StructuredLogger("new", level="info")
        await new_log.load_state(state)
        assert new_log._level == "debug"
        await log.shutdown()
        await new_log.shutdown()
