"""Tests for RecoverySystem."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.events.bus import EventBus, SystemEvent
from core.logging.structured_logger import StructuredLogger
from core.recovery.system import RecoverySystem
from tests.conftest import InMemoryBackend


@pytest_asyncio.fixture
async def recovery(
    event_bus: EventBus,
    persistence: InMemoryBackend,
    logger: StructuredLogger,
) -> AsyncGenerator[RecoverySystem, None]:
    rec = RecoverySystem(
        event_bus=event_bus,
        persistence=persistence,
        logger=logger,
    )
    yield rec
    await rec.shutdown()


class TestRecoverySystem:
    async def test_clean_shutdown_no_recovery(
        self,
        event_bus: EventBus,
        persistence: InMemoryBackend,
        logger: StructuredLogger,
    ) -> None:
        await persistence.save(
            "recovery.crash_state",
            {"crashed": False, "last_clean_shutdown": datetime.now(timezone.utc).isoformat()},
        )
        rec = RecoverySystem(
            event_bus=event_bus,
            persistence=persistence,
            logger=logger,
        )
        await rec.initialize()
        assert rec._initialized is True

    async def test_crash_detection(
        self,
        event_bus: EventBus,
        persistence: InMemoryBackend,
        logger: StructuredLogger,
    ) -> None:
        await persistence.save(
            "recovery.crash_state",
            {"crashed": True, "reason": "test"},
        )
        rec = RecoverySystem(
            event_bus=event_bus,
            persistence=persistence,
            logger=logger,
        )
        await rec.initialize()
        assert rec._initialized is True

    async def test_no_crash_state_triggers_recovery(
        self,
        event_bus: EventBus,
        persistence: InMemoryBackend,
        logger: StructuredLogger,
    ) -> None:
        rec = RecoverySystem(
            event_bus=event_bus,
            persistence=persistence,
            logger=logger,
        )
        await rec.initialize()
        assert rec._initialized is True

    async def test_take_snapshot(self, recovery: RecoverySystem) -> None:
        states = {"runtime": {"tick": 42}, "registry": {"count": 5}}
        await recovery.take_snapshot(tick_count=42, subsystem_states=states)
        saved = await recovery._persistence.load("recovery.snapshot")
        assert saved is not None
        assert saved["tick_count"] == 42
        assert saved["subsystems"]["runtime"]["tick"] == 42

    async def test_shutdown_records_clean_state(self, recovery: RecoverySystem) -> None:
        await recovery.shutdown()
        state = await recovery._persistence.load("recovery.crash_state")
        assert state is not None
        assert state["crashed"] is False

    async def test_save_and_load_state(self, recovery: RecoverySystem) -> None:
        state = await recovery.save_state()
        assert isinstance(state, dict)
        await recovery.load_state(state)
        assert recovery._initialized is True
