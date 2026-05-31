"""Async event bus with typed topics, subscribers, filtering, and replay."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Coroutine


class EventPriority(IntEnum):
    """Priority levels for event delivery."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class SystemEvent:
    """A typed event flowing through the bus.

    Attributes:
        topic: Dot-separated event topic (e.g. 'agent.spawned').
        priority: Delivery priority for ordering.
        payload: Arbitrary JSON-serializable data.
        source: Optional identifier of the emitting subsystem.
        correlation_id: Optional grouping identifier for tracing.
        timestamp: ISO-8601 timestamp; auto-set if omitted.
    """

    topic: str
    priority: EventPriority = EventPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    correlation_id: str | None = None
    timestamp: str | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemEvent:
        data["priority"] = EventPriority(data["priority"])
        return cls(**data)


EventFilter = Callable[[SystemEvent], bool]
EventHandler = Callable[[SystemEvent], Coroutine[Any, Any, None]]


@dataclass
class EventSubscription:
    """Describes a registered subscriber."""

    topic_pattern: str
    handler: EventHandler
    filters: list[EventFilter] = field(default_factory=list)
    priority: EventPriority | None = None
    id: int = field(default_factory=lambda: id(object()))


class EventBus:
    """Async pub/sub event bus.

    Supports topic-based subscriptions with glob-style patterns,
    per-subscriber filters, priority ordering, and event replay
    for recovery scenarios.
    """

    def __init__(self, max_queue_size: int = 10_000) -> None:
        self._subscriptions: dict[str, list[EventSubscription]] = defaultdict(list)
        self._history: list[SystemEvent] = []
        self._history_limit: int = 10_000
        self._max_queue_size = max_queue_size
        self._queue: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: asyncio.Task[None] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Start the event bus worker."""
        self._initialized = True
        self._worker_task = asyncio.create_task(self._dispatch_loop())
        await self.publish(
            SystemEvent(
                topic="system.bus.initialized",
                priority=EventPriority.CRITICAL,
                source="events.bus",
            )
        )

    async def shutdown(self) -> None:
        """Stop the event bus and drain pending events."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        self._initialized = False
        self._history.clear()

    async def save_state(self) -> dict[str, Any]:
        """Serialize event bus state for persistence."""
        return {
            "history": [e.to_dict() for e in self._history[-100:]],
            "history_limit": self._history_limit,
        }

    @property
    def history(self) -> list[SystemEvent]:
        return list(self._history)

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore event bus state from serialized data."""
        if not state:
            return
        self._history.clear()
        self._history_limit = state.get("history_limit", self._history_limit)
        for entry in state.get("history", []):
            self._history.append(SystemEvent.from_dict(entry))

    def subscribe(
        self,
        topic_pattern: str,
        handler: EventHandler,
        filters: list[EventFilter] | None = None,
        priority: EventPriority | None = None,
    ) -> EventSubscription:
        """Register an event handler for a topic pattern.

        Args:
            topic_pattern: Exact topic or glob pattern (e.g. 'agent.*').
            handler: Async callable accepting a SystemEvent.
            filters: Optional list of predicate callables.
            priority: If set, only receive events of this priority or higher.

        Returns:
            EventSubscription that can be used to unsubscribe.
        """
        sub = EventSubscription(
            topic_pattern=topic_pattern,
            handler=handler,
            filters=filters or [],
            priority=priority,
        )
        self._subscriptions[topic_pattern].append(sub)
        return sub

    def unsubscribe(self, subscription: EventSubscription) -> None:
        """Remove a previously registered subscription."""
        for pattern, subs in list(self._subscriptions.items()):
            if subscription in subs:
                subs.remove(subscription)
                if not subs:
                    del self._subscriptions[pattern]
                break

    async def publish(self, event: SystemEvent) -> None:
        """Publish an event to the bus.

        The event is queued for async delivery to matching subscribers
        and appended to the history ring for replay.
        """
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

        await self._queue.put(event)

    def replay(
        self,
        topic_filter: str | None = None,
        since: str | None = None,
    ) -> list[SystemEvent]:
        """Return matching events from history for replay/recovery.

        Args:
            topic_filter: Optional topic pattern to filter by.
            since: Optional ISO-8601 timestamp; only return events after this.

        Returns:
            List of matching SystemEvent objects.
        """
        events = self._history
        if since:
            events = [e for e in events if e.timestamp >= since]
        if topic_filter:
            events = [e for e in events if self._topic_matches(e.topic, topic_filter)]
        return events

    async def _dispatch_loop(self) -> None:
        """Background loop delivering queued events to subscribers."""
        while True:
            try:
                event = await self._queue.get()
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _dispatch(self, event: SystemEvent) -> None:
        """Deliver an event to all matching subscribers."""
        tasks: list[Coroutine[Any, Any, None]] = []
        for pattern, subs in self._subscriptions.items():
            if not self._topic_matches(event.topic, pattern):
                continue
            for sub in subs:
                if sub.priority is not None and event.priority > sub.priority:
                    continue
                if not all(f(event) for f in sub.filters):
                    continue
                tasks.append(sub.handler(event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check if a topic matches a pattern (supports * and ** wildcards)."""
        if pattern == "**":
            return True
        if pattern.endswith(".**"):
            prefix = pattern[:-3]
            return topic.startswith(prefix)
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic == prefix or topic.startswith(prefix + ".")
        return topic == pattern
