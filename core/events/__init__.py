"""Event system package."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.events.bus import EventBus, SystemEvent, EventPriority, EventSubscription

__all__ = ["EventBus", "SystemEvent", "EventPriority", "EventSubscription", "bus"]


class _SyncBusBridge:
    """Synchronous bridge to the async EventBus for simple emit patterns."""

    def __init__(self, async_bus: EventBus) -> None:
        self._bus = async_bus

    def emit(
        self,
        event_type: str,
        agent_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SystemEvent:
        event = SystemEvent(
            topic=event_type,
            priority=EventPriority.NORMAL,
            payload={
                **(payload or {}),
            },
            source=agent_id,
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._bus.publish(event))
            else:
                loop.run_until_complete(self._bus.publish(event))
        except RuntimeError:
            asyncio.run(self._bus.publish(event))
        return event


_instance: EventBus | None = None


def get_bus() -> EventBus:
    global _instance
    if _instance is None:
        _instance = EventBus()
        try:
            asyncio.run(_instance.initialize())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_instance.initialize())
    return _instance


bus = _SyncBusBridge(get_bus())
