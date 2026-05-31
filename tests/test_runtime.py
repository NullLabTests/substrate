"""Tests for RuntimeEngine."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry
from core.runtime.engine import RuntimeEngine, RuntimeState
from core.scheduler.tick_scheduler import TickScheduler
from core.telemetry.pipeline import TelemetryPipeline
from core.recovery.system import RecoverySystem
from tests.conftest import InMemoryBackend


@pytest_asyncio.fixture
async def engine(
    event_bus: EventBus,
    registry: AgentRegistry,
    scheduler: TickScheduler,
    telemetry: TelemetryPipeline,
    logger: StructuredLogger,
) -> AsyncGenerator[RuntimeEngine, None]:
    persistence = InMemoryBackend()
    await persistence.initialize()
    recovery = RecoverySystem(event_bus=event_bus, persistence=persistence, logger=logger)
    eng = RuntimeEngine(
        event_bus=event_bus,
        agent_registry=registry,
        tick_scheduler=scheduler,
        persistence=persistence,
        telemetry=telemetry,
        logger=logger,
        recovery=recovery,
        tick_interval=0.01,
    )
    await eng.initialize()
    yield eng
    await eng.shutdown()


class TestRuntimeEngine:
    async def test_initial_state(self, engine: RuntimeEngine) -> None:
        assert engine.state in (RuntimeState.CREATED, RuntimeState.RUNNING)

    async def test_tick_count_starts_at_zero(self, engine: RuntimeEngine) -> None:
        assert engine.tick_count == 0

    async def test_run_and_stop(self, engine: RuntimeEngine) -> None:
        run_task = asyncio.create_task(engine.run())
        await asyncio.sleep(0.05)
        assert engine.state == RuntimeState.RUNNING
        assert engine.tick_count > 0
        await engine.stop()
        await asyncio.sleep(0.05)
        assert engine.state == RuntimeState.STOPPED

    async def test_save_and_load_state(self, engine: RuntimeEngine) -> None:
        await engine.save_state()
        loaded = await engine.load_state()
        assert loaded is not None
        assert "tick_count" in loaded
        assert "state" in loaded

    async def test_register_tick_hook(self, engine: RuntimeEngine) -> None:
        ticks_seen: list[int] = []

        async def hook(tick: int) -> None:
            ticks_seen.append(tick)

        engine.register_tick_hook(hook)
        run_task = asyncio.create_task(engine.run())
        await asyncio.sleep(0.05)
        await engine.stop()
        await asyncio.sleep(0.02)
        assert len(ticks_seen) > 0

    async def test_graceful_shutdown(self, engine: RuntimeEngine) -> None:
        run_task = asyncio.create_task(engine.run())
        await asyncio.sleep(0.03)
        assert engine.state == RuntimeState.RUNNING
        await engine.shutdown()
        assert engine.state == RuntimeState.STOPPED
