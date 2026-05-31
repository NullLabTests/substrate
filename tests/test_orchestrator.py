"""Tests for the Orchestrator integration layer."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry
from core.runtime.engine import RuntimeEngine
from core.scheduler.tick_scheduler import TickScheduler
from core.telemetry.pipeline import TelemetryPipeline
from core.events.bus import SystemEvent, EventPriority
from config.settings import Settings
from orchestrator import Orchestrator
from tests.conftest import InMemoryBackend


@pytest_asyncio.fixture
async def orchestrator() -> AsyncGenerator[Orchestrator, None]:
    """Fixture providing an initialized Orchestrator with in-memory persistence."""
    settings = Settings(
        tick_interval=0.01,
        log_level="debug",
        db_path=":memory:",
    )
    orch = Orchestrator(settings=settings)
    # Inject in-memory persistence backend before initialize() wires subsystems
    persistence = InMemoryBackend()
    await persistence.initialize()
    orch._persistence = persistence
    # Override _build_persistence to return the in-memory backend
    async def _fake_build() -> InMemoryBackend:
        return persistence
    orch._build_persistence = _fake_build  # type: ignore[method-assign]
    await orch.initialize()
    yield orch
    await orch.shutdown()


class TestOrchestrator:
    """Test suite for the Orchestrator integration layer."""

    async def test_initialize(self, orchestrator: Orchestrator) -> None:
        """Orchestrator initializes all subsystems."""
        assert orchestrator.runtime is not None
        assert orchestrator.event_bus is not None
        assert orchestrator.registry is not None
        assert orchestrator.scheduler is not None
        assert orchestrator.telemetry is not None
        assert orchestrator.logger is not None

    async def test_initialized_state(self, orchestrator: Orchestrator) -> None:
        """Runtime engine is in CREATED state after initialization."""
        assert orchestrator.runtime.state == "created"

    async def test_shutdown(self, orchestrator: Orchestrator) -> None:
        """Orchestrator shutdown stops all subsystems."""
        await orchestrator.shutdown()
        # After shutdown, the runtime should be in STOPPED state
        assert orchestrator.runtime.state == "stopped"

    async def test_save_and_load_state(self, orchestrator: Orchestrator) -> None:
        """Save and load state round-trips all subsystem states."""
        # Run a few ticks to generate state
        run_task = asyncio.create_task(orchestrator.runtime.run())
        await asyncio.sleep(0.05)
        await orchestrator.runtime.stop()
        await run_task

        # Save system state — this persists to the in-memory backend
        await orchestrator.save_state()

        # Get the persistence backend (has the saved state)
        persisted = orchestrator._persistence

        # Load into a new orchestrator using the same persistence backend
        settings = Settings(tick_interval=0.01, log_level="debug", db_path=":memory:")
        orch2 = Orchestrator(settings=settings)
        # Inject same in-memory backend so state is available
        async def _fake_build() -> InMemoryBackend:
            return persisted  # type: ignore[return-value]
        orch2._build_persistence = _fake_build  # type: ignore[method-assign]
        orch2._persistence = persisted
        await orch2.initialize()
        await orch2.load_state()

        assert orch2.runtime is not None
        assert orch2.runtime.tick_count > 0
        await orch2.shutdown()

    async def test_double_shutdown_safe(self, orchestrator: Orchestrator) -> None:
        """Calling shutdown twice is safe (idempotent)."""
        await orchestrator.shutdown()
        await orchestrator.shutdown()  # Should not raise

    async def test_runtime_accessor(self, orchestrator: Orchestrator) -> None:
        """Runtime accessor returns the RuntimeEngine."""
        rt = orchestrator.runtime
        assert isinstance(rt, RuntimeEngine)

    async def test_event_bus_accessor(self, orchestrator: Orchestrator) -> None:
        """Event bus accessor returns the EventBus."""
        bus = orchestrator.event_bus
        assert isinstance(bus, EventBus)

    async def test_registry_accessor(self, orchestrator: Orchestrator) -> None:
        """Registry accessor returns the AgentRegistry."""
        reg = orchestrator.registry
        assert isinstance(reg, AgentRegistry)

    async def test_scheduler_accessor(self, orchestrator: Orchestrator) -> None:
        """Scheduler accessor returns the TickScheduler."""
        sched = orchestrator.scheduler
        assert isinstance(sched, TickScheduler)

    async def test_telemetry_accessor(self, orchestrator: Orchestrator) -> None:
        """Telemetry accessor returns the TelemetryPipeline."""
        tel = orchestrator.telemetry
        assert isinstance(tel, TelemetryPipeline)

    async def test_logger_accessor(self, orchestrator: Orchestrator) -> None:
        """Logger accessor returns the StructuredLogger."""
        log = orchestrator.logger
        assert isinstance(log, StructuredLogger)

    async def test_event_flow_through_system(self, orchestrator: Orchestrator) -> None:
        """Events can be published and received through the wired system."""
        received: list = []

        async def handler(event) -> None:
            received.append(event)

        orchestrator.event_bus.subscribe("test.flow", handler)
        await orchestrator.event_bus.publish(
            SystemEvent(
                topic="test.flow",
                payload={"msg": "hello"},
            )
        )
        await asyncio.sleep(0.02)
        assert len(received) == 1
        assert received[0].payload["msg"] == "hello"

    async def test_agent_registration_through_system(
        self, orchestrator: Orchestrator
    ) -> None:
        """Agents can be registered and queried through the wired system."""
        meta = orchestrator.registry.register(
            "test-agent-1", "TestAgent", "worker", {"key": "val"}
        )
        assert meta.id == "test-agent-1"
        fetched = orchestrator.registry.get("test-agent-1")
        assert fetched is not None
        assert fetched.metadata["key"] == "val"

    async def test_scheduler_ticks_through_runtime(
        self, orchestrator: Orchestrator
    ) -> None:
        """The runtime processes ticks through the scheduler."""
        run_task = asyncio.create_task(orchestrator.runtime.run())
        await asyncio.sleep(0.05)
        await orchestrator.runtime.stop()
        await run_task
        assert orchestrator.runtime.tick_count > 0
