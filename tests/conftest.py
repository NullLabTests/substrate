"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend
from core.registry.agent_registry import AgentRegistry
from core.scheduler.tick_scheduler import TickScheduler
from core.telemetry.pipeline import TelemetryPipeline
from core.recovery.system import RecoverySystem


class InMemoryBackend(PersistenceBackend):
    """In-memory persistence backend for tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, object]] = {}

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        self._data.clear()

    async def save(self, key: str, value: dict[str, object]) -> None:
        self._data[key] = value

    async def load(self, key: str) -> dict[str, object] | None:
        return self._data.get(key)

    async def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    async def list_keys(self, prefix: str = "") -> list[str]:
        return sorted(k for k in self._data if k.startswith(prefix))


@pytest_asyncio.fixture
async def event_bus() -> AsyncGenerator[EventBus, None]:
    bus = EventBus()
    await bus.initialize()
    yield bus
    await bus.shutdown()


@pytest_asyncio.fixture
async def logger() -> AsyncGenerator[StructuredLogger, None]:
    log = StructuredLogger("test", level="debug")
    await log.initialize()
    yield log
    await log.shutdown()


@pytest_asyncio.fixture
async def persistence() -> AsyncGenerator[InMemoryBackend, None]:
    backend = InMemoryBackend()
    await backend.initialize()
    yield backend
    await backend.shutdown()


@pytest_asyncio.fixture
async def registry() -> AsyncGenerator[AgentRegistry, None]:
    reg = AgentRegistry()
    await reg.initialize()
    yield reg
    await reg.shutdown()


@pytest_asyncio.fixture
async def scheduler(logger: StructuredLogger) -> AsyncGenerator[TickScheduler, None]:
    sched = TickScheduler(logger=logger)
    await sched.initialize()
    yield sched
    await sched.shutdown()


@pytest_asyncio.fixture
async def telemetry() -> AsyncGenerator[TelemetryPipeline, None]:
    tel = TelemetryPipeline()
    await tel.initialize()
    yield tel
    await tel.shutdown()
