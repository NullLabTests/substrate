"""Simulation runtime engine.

Manages the lifecycle of all subsystems in a tick-based main loop.
Handles graceful shutdown via asyncio signals.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from core.events.bus import EventBus
from core.events.bus import SystemEvent, EventPriority
from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend
from core.registry.agent_registry import AgentRegistry
from core.scheduler.tick_scheduler import TickScheduler
from core.telemetry.pipeline import TelemetryPipeline
from core.recovery.system import RecoverySystem


class RuntimeState:
    """Enum-like container for runtime states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class RuntimeEngine:
    """Core simulation runtime engine.

    Coordinates all subsystems through the simulation lifecycle.
    Runs a tick-based main loop that drives the event bus, scheduler,
    registry, persistence, telemetry, and logging subsystems.

    Attributes:
        state: Current runtime state string.
        tick_count: Total ticks processed since start.
        started_at: UTC datetime when the engine last entered RUNNING state.
    """

    def __init__(
        self,
        event_bus: EventBus,
        agent_registry: AgentRegistry,
        tick_scheduler: TickScheduler,
        persistence: PersistenceBackend,
        telemetry: TelemetryPipeline,
        logger: StructuredLogger,
        recovery: RecoverySystem,
        tick_interval: float = 0.1,
    ) -> None:
        self._event_bus = event_bus
        self._agent_registry = agent_registry
        self._tick_scheduler = tick_scheduler
        self._persistence = persistence
        self._telemetry = telemetry
        self._logger = logger
        self._recovery = recovery

        self._tick_interval = tick_interval
        self._state = RuntimeState.CREATED
        self._tick_count: int = 0
        self._started_at: datetime | None = None
        self._shutdown_event = asyncio.Event()
        self._tick_hooks: list[Callable[[int], Coroutine[Any, Any, None]]] = []
        self._main_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    async def initialize(self) -> None:
        """Initialize all subsystems and prepare for running."""
        self._state = RuntimeState.INITIALIZING
        self._logger.info("runtime_initializing", subsystem="engine")

        await self._recovery.initialize()
        await self._event_bus.initialize()
        await self._agent_registry.initialize()
        await self._tick_scheduler.initialize()
        await self._persistence.initialize()
        await self._telemetry.initialize()

        self._logger.info("runtime_initialized", subsystem="engine")
        self._state = RuntimeState.CREATED

    async def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        self._state = RuntimeState.SHUTTING_DOWN
        self._logger.info("runtime_shutting_down", subsystem="engine")

        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        await self.save_state()

        await self._telemetry.shutdown()
        await self._persistence.shutdown()
        await self._tick_scheduler.shutdown()
        await self._agent_registry.shutdown()
        await self._event_bus.shutdown()
        await self._recovery.shutdown()

        self._state = RuntimeState.STOPPED
        self._logger.info("runtime_stopped", subsystem="engine")

    async def save_state(self) -> None:
        """Persist runtime state snapshot."""
        snapshot = {
            "state": self._state,
            "tick_count": self._tick_count,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._persistence.save("runtime_state", snapshot)
        self._logger.debug("runtime_state_saved", tick_count=self._tick_count)

    async def load_state(self) -> dict[str, Any]:
        """Restore runtime state from persistence."""
        data = await self._persistence.load("runtime_state")
        if data:
            self._tick_count = data.get("tick_count", 0)
            started = data.get("started_at")
            if started:
                self._started_at = datetime.fromisoformat(started)
            self._logger.info("runtime_state_loaded", tick_count=self._tick_count)
        return data or {}

    def register_tick_hook(
        self, hook: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a coroutine hook called after each tick.

        Args:
            hook: Async callable receiving the current tick number.
        """
        self._tick_hooks.append(hook)

    async def _process_tick(self, tick: int) -> None:
        """Process a single simulation tick."""
        await self._event_bus.publish(
            SystemEvent(
                topic="system.tick",
                priority=EventPriority.NORMAL,
                payload={"tick": tick, "timestamp": datetime.now(timezone.utc).isoformat()},
            )
        )
        await self._agent_registry.heartbeat_all()

        for hook in self._tick_hooks:
            await hook(tick)

        self._telemetry.record("ticks", 1)
        self._tick_count = tick

    async def run(self) -> None:
        """Start the main simulation loop.

        Blocks until shutdown is requested via signal or stop().
        """
        self._state = RuntimeState.RUNNING
        self._started_at = datetime.now(timezone.utc)
        self._shutdown_event.clear()
        self._logger.info(
            "runtime_started",
            tick_interval=self._tick_interval,
            started_at=self._started_at.isoformat(),
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_handler)
            except NotImplementedError:
                pass

        self._main_task = asyncio.create_task(self._main_loop())

        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    def _signal_handler(self) -> None:
        """Handle OS signals by scheduling shutdown."""
        self._shutdown_event.set()

    async def stop(self) -> None:
        """Request graceful shutdown from outside."""
        self._logger.info("runtime_stop_requested")
        self._shutdown_event.set()

    async def _main_loop(self) -> None:
        """Core tick loop executed as an asyncio Task."""
        try:
            async with self._tick_scheduler.ticks(self._tick_interval) as ticker:
                async for tick in ticker:
                    if self._state == RuntimeState.SHUTTING_DOWN:
                        break
                    await self._process_tick(tick)

                    if self._tick_count % 100 == 0:
                        await self.save_state()
        except asyncio.CancelledError:
            self._logger.debug("main_loop_cancelled")
            raise

    @asynccontextmanager
    async def managed_run(self):
        """Context manager for safe run lifecycle."""
        try:
            await self.initialize()
            task = asyncio.create_task(self.run())
            yield self
        finally:
            await self.shutdown()
            task.cancel() if task and not task.done() else None
