"""Tick scheduler driving simulation ticks at configurable intervals."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from core.events.bus import EventPriority, SystemEvent
from core.logging.structured_logger import StructuredLogger


class TickScheduler:
    """Drives simulation ticks at configurable intervals.

     Supports pause/resume, tick counting, and pre/post tick hooks.
    """

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self._paused = False
        self._tick_count: int = 0
        self._started_at: datetime | None = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._initialized = False
        self._pre_hooks: list[Callable[[int], Coroutine[Any, Any, None]]] = []
        self._post_hooks: list[Callable[[int], Coroutine[Any, Any, None]]] = []
        self._logger = logger

    async def initialize(self) -> None:
        """Prepare the scheduler."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Stop the scheduler and clear state."""
        self._paused = False
        self._tick_count = 0
        self._pre_hooks.clear()
        self._post_hooks.clear()
        self._initialized = False

    async def save_state(self) -> dict[str, Any]:
        """Return serializable scheduler state."""
        return {
            "tick_count": self._tick_count,
            "paused": self._paused,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore scheduler state from serialized data."""
        if not state:
            return
        self._tick_count = state.get("tick_count", 0)
        self._paused = state.get("paused", False)
        started = state.get("started_at")
        if started:
            self._started_at = datetime.fromisoformat(started)

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_running(self) -> bool:
        return self._initialized and not self._paused

    def pause(self) -> None:
        """Pause the tick loop."""
        self._paused = True
        self._pause_event.clear()
        if self._logger:
            self._logger.debug("scheduler_paused")

    def resume(self) -> None:
        """Resume the tick loop."""
        self._paused = False
        self._pause_event.set()
        if self._logger:
            self._logger.debug("scheduler_resumed")

    def add_pre_hook(
        self, hook: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a hook called before each tick.

        Args:
            hook: Async callable receiving the tick number.
        """
        self._pre_hooks.append(hook)

    def add_post_hook(
        self, hook: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a hook called after each tick.

        Args:
            hook: Async callable receiving the tick number.
        """
        self._post_hooks.append(hook)

    @asynccontextmanager
    async def ticks(self, interval: float = 0.1) -> AsyncIterator[AsyncIterator[int]]:
        """Context manager yielding an async iterator of tick numbers.

        Usage:
            async with scheduler.ticks(0.05) as ticker:
                async for tick in ticker:
                    ...

        Args:
            interval: Seconds between ticks.

        Yields:
            An async iterator that produces incrementing tick integers.
        """

        async def tick_generator() -> AsyncIterator[int]:
            self._started_at = datetime.now(timezone.utc)
            while True:
                await self._pause_event.wait()
                for hook in self._pre_hooks:
                    await hook(self._tick_count)
                self._tick_count += 1
                try:
                    yield self._tick_count
                except GeneratorExit:
                    for hook in self._post_hooks:
                        await hook(self._tick_count)
                    break
                for hook in self._post_hooks:
                    await hook(self._tick_count)
                await asyncio.sleep(interval)

        yield tick_generator()
