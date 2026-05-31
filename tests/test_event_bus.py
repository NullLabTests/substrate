"""Tests for EventBus."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.events.bus import EventBus, SystemEvent, EventPriority


class TestEventBus:
    async def test_initialize_shutdown(self, event_bus: EventBus) -> None:
        assert event_bus._initialized is True
        await event_bus.shutdown()
        assert event_bus._initialized is False

    async def test_publish_and_subscribe(self, event_bus: EventBus) -> None:
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        event_bus.subscribe("test.topic", handler)
        await event_bus.publish(
            SystemEvent(topic="test.topic", payload={"key": "val"})
        )
        await asyncio.sleep(0.02)
        assert len(received) == 1
        assert received[0].topic == "test.topic"
        assert received[0].payload == {"key": "val"}

    async def test_unsubscribe(self, event_bus: EventBus) -> None:
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        sub = event_bus.subscribe("test.topic", handler)
        event_bus.unsubscribe(sub)
        await event_bus.publish(
            SystemEvent(topic="test.topic", payload={})
        )
        await asyncio.sleep(0.02)
        assert len(received) == 0

    async def test_topic_wildcard(self, event_bus: EventBus) -> None:
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        event_bus.subscribe("agents.*", handler)
        await event_bus.publish(
            SystemEvent(topic="agents.spawned", payload={})
        )
        await event_bus.publish(
            SystemEvent(topic="agents.died", payload={})
        )
        await event_bus.publish(
            SystemEvent(topic="system.tick", payload={})
        )
        await asyncio.sleep(0.02)
        assert len(received) == 2

    async def test_priority_filtering(self, event_bus: EventBus) -> None:
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        event_bus.subscribe(
            "test.priority", handler, priority=EventPriority.HIGH
        )
        await event_bus.publish(
            SystemEvent(topic="test.priority", priority=EventPriority.CRITICAL, payload={})
        )
        await event_bus.publish(
            SystemEvent(topic="test.priority", priority=EventPriority.NORMAL, payload={})
        )
        await asyncio.sleep(0.02)
        assert len(received) == 1

    async def test_event_filtering(self, event_bus: EventBus) -> None:
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        event_bus.subscribe(
            "test.filter",
            handler,
            filters=[lambda e: e.payload.get("important") is True],
        )
        await event_bus.publish(
            SystemEvent(topic="test.filter", payload={"important": True})
        )
        await event_bus.publish(
            SystemEvent(topic="test.filter", payload={"important": False})
        )
        await asyncio.sleep(0.02)
        assert len(received) == 1

    async def test_replay(self, event_bus: EventBus) -> None:
        await event_bus.publish(
            SystemEvent(topic="replay.test", payload={"seq": 1})
        )
        await event_bus.publish(
            SystemEvent(topic="replay.test", payload={"seq": 2})
        )
        events = event_bus.replay(topic_filter="replay.test")
        assert len(events) == 2

    async def test_save_and_load_state(self, event_bus: EventBus) -> None:
        await event_bus.publish(
            SystemEvent(topic="state.test", payload={"x": 1})
        )
        state = await event_bus.save_state()
        assert len(state["history"]) > 0

        new_bus = EventBus()
        await new_bus.load_state(state)
        assert len(new_bus.history) > 0
        topics = [e.topic for e in new_bus.history]
        assert "state.test" in topics
