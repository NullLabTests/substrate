"""Orchestrator integration module.

Wires all subsystems together and provides a unified Orchestrator class
for lifecycle management, state persistence, and recovery.
"""

from __future__ import annotations

from typing import Any

from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend
from core.recovery.system import RecoverySystem
from core.registry.agent_registry import AgentRegistry
from core.runtime.engine import RuntimeEngine
from core.scheduler.tick_scheduler import TickScheduler
from core.telemetry.pipeline import TelemetryPipeline
from config.settings import Settings


class Orchestrator:
    """Top-level integration point for the substrate system.

    Initializes all subsystems in dependency order, provides
    lifecycle management, and coordinates state persistence.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

        self._logger = StructuredLogger(
            name="platform",
            level=self._settings.log_level,
            file_path=self._settings.log_file,
        )
        self._event_bus = EventBus()
        self._agent_registry = AgentRegistry()
        self._tick_scheduler = TickScheduler(logger=self._logger)
        self._telemetry = TelemetryPipeline()
        self._persistence: PersistenceBackend | None = None
        self._recovery: RecoverySystem | None = None
        self._runtime: RuntimeEngine | None = None

    async def initialize(self) -> None:
        """Initialize all subsystems in dependency order."""
        await self._logger.initialize()
        self._logger.info("orchestrator_initializing")

        self._persistence = await self._build_persistence()
        await self._persistence.initialize()

        self._recovery = RecoverySystem(
            event_bus=self._event_bus,
            persistence=self._persistence,
            logger=self._logger,
        )

        self._runtime = RuntimeEngine(
            event_bus=self._event_bus,
            agent_registry=self._agent_registry,
            tick_scheduler=self._tick_scheduler,
            persistence=self._persistence,
            telemetry=self._telemetry,
            logger=self._logger,
            recovery=self._recovery,
            tick_interval=self._settings.tick_interval,
        )

        await self._runtime.initialize()
        self._logger.info("orchestrator_initialized")

    async def shutdown(self) -> None:
        """Shut down all subsystems in reverse dependency order."""
        self._logger.info("orchestrator_shutting_down")
        if self._runtime:
            await self._runtime.shutdown()

        self._recovery and await self._recovery.shutdown()
        self._persistence and await self._persistence.shutdown()
        await self._telemetry.shutdown()
        await self._logger.shutdown()

    async def save_state(self) -> None:
        """Save state for all subsystems.

        Persists individual subsystem states to the key-value store,
        and also stores a combined recovery snapshot.
        """
        if not self._runtime:
            return
        states: dict[str, dict[str, Any]] = {}

        runtime_state = await self._runtime.save_state()
        states["runtime"] = runtime_state
        if self._persistence:
            await self._persistence.save("runtime_state", runtime_state)

        bus_state = await self._event_bus.save_state()
        states["event_bus"] = bus_state
        if self._persistence:
            await self._persistence.save("event_bus", bus_state)

        reg_state = await self._agent_registry.save_state()
        states["registry"] = reg_state
        if self._persistence:
            await self._persistence.save("registry", reg_state)

        sched_state = await self._tick_scheduler.save_state()
        states["scheduler"] = sched_state
        if self._persistence:
            await self._persistence.save("scheduler", sched_state)

        states["telemetry"] = await self._telemetry.save_state()
        states["logger"] = await self._logger.save_state()

        if self._recovery:
            await self._recovery.take_snapshot(
                tick_count=self._runtime.tick_count,
                subsystem_states=states,
            )

    async def load_state(self) -> None:
        """Load state for all subsystems from persistence."""
        if not self._runtime:
            return

        await self._runtime.load_state()
        bus_state = await self._persistence.load("event_bus") if self._persistence else None
        if bus_state:
            await self._event_bus.load_state(bus_state)

        reg_state = await self._persistence.load("registry") if self._persistence else None
        if reg_state:
            await self._agent_registry.load_state(reg_state)

        sched_state = await self._persistence.load("scheduler") if self._persistence else None
        if sched_state:
            await self._tick_scheduler.load_state(sched_state)

        self._logger.info("orchestrator_state_loaded")

    @property
    def runtime(self) -> RuntimeEngine | None:
        return self._runtime

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def registry(self) -> AgentRegistry:
        return self._agent_registry

    @property
    def scheduler(self) -> TickScheduler:
        return self._tick_scheduler

    @property
    def telemetry(self) -> TelemetryPipeline:
        return self._telemetry

    @property
    def logger(self) -> StructuredLogger:
        return self._logger

    async def _build_persistence(self) -> PersistenceBackend:
        """Create the persistence backend based on settings."""
        from storage.sqlite.backend import SQLiteBackend

        return SQLiteBackend(
            db_path=self._settings.db_path,
            logger=self._logger,
        )
