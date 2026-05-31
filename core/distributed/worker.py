from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from core.distributed.message_queue import MessageQueueBackend
from core.distributed.protocol import (
    DistributedMessage,
    Heartbeat,
    MessageType,
    TickAssignment,
    TickResult,
)
from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry


@dataclass
class WorkerConfig:
    worker_id: str
    coordinator_id: str = "coordinator"
    heartbeat_interval: float = 5.0
    tick_timeout: float = 30.0
    max_concurrent_ticks: int = 10
    channel: str = "default"


class WorkerNode:
    def __init__(
        self,
        config: WorkerConfig,
        message_queue: MessageQueueBackend,
        event_bus: EventBus,
        registry: AgentRegistry,
        logger: StructuredLogger,
        agent_processors: dict[str, Any] | None = None,
    ) -> None:
        self._config = config
        self._mq = message_queue
        self._event_bus = event_bus
        self._registry = registry
        self._log = logger
        self._agent_processors: dict[str, Any] = agent_processors or {}
        self._running = False
        self._current_tick: int | None = None
        self._load: float = 0.0
        self._ticks_processed: int = 0
        self._events_generated: int = 0
        self._errors: int = 0

    async def start(self) -> None:
        self._running = True
        self._log.info(
            "worker_started",
            worker_id=self._config.worker_id,
            coordinator_id=self._config.coordinator_id,
        )
        await asyncio.gather(
            self._heartbeat_loop(),
            self._message_loop(),
        )

    async def stop(self) -> None:
        self._running = False
        self._log.info("worker_stopped", worker_id=self._config.worker_id)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            heartbeat = Heartbeat(
                node_id=self._config.worker_id,
                node_type="worker",
                tick=self._current_tick or 0,
                load=self._load,
                alive=True,
            )
            await self._mq.publish(
                heartbeat.to_message(), channel=self._config.channel
            )
            await asyncio.sleep(self._config.heartbeat_interval)

    async def _message_loop(self) -> None:
        async for msg in self._mq.subscribe(self._config.channel):
            if not self._running:
                break
            if msg.destination_id not in (self._config.worker_id, "*", ""):
                continue
            try:
                await self._handle_message(msg)
            except Exception as exc:
                self._log.error(
                    "worker_message_error",
                    worker_id=self._config.worker_id,
                    msg_type=msg.msg_type.value,
                    error=str(exc),
                )
                self._errors += 1

    async def _handle_message(self, msg: DistributedMessage) -> None:
        if msg.msg_type == MessageType.TICK_ASSIGNMENT:
            await self._process_tick(TickAssignment.from_message(msg))
        elif msg.msg_type == MessageType.SHUTDOWN:
            await self.stop()
        elif msg.msg_type == MessageType.GLOBAL_EVENT:
            await self._event_bus.publish_raw(msg.payload)

    async def _process_tick(self, assignment: TickAssignment) -> None:
        self._current_tick = assignment.tick
        t0 = time.monotonic()
        agent_results: dict[str, dict[str, Any]] = {}
        local_events: list[dict[str, Any]] = []
        success = True
        error: str | None = None

        try:
            sem = asyncio.Semaphore(self._config.max_concurrent_ticks)
            async def process_agent(aid: str) -> tuple[str, dict[str, Any]]:
                async with sem:
                    result = await self._tick_agent(aid, assignment)
                    return aid, result

            tasks = [process_agent(aid) for aid in assignment.agent_ids]
            for coro in asyncio.as_completed(tasks):
                aid, result = await coro
                agent_results[aid] = result
                if result.get("events"):
                    local_events.extend(result["events"])
        except Exception as exc:
            success = False
            error = str(exc)
            self._log.error(
                "tick_failed",
                worker_id=self._config.worker_id,
                tick=assignment.tick,
                error=error,
            )
            self._errors += 1

        duration_ms = (time.monotonic() - t0) * 1000
        result = TickResult(
            worker_id=self._config.worker_id,
            tick=assignment.tick,
            agent_results=agent_results,
            local_events=local_events,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
        await self._mq.publish(
            result.to_message(), channel=self._config.channel
        )
        self._ticks_processed += 1
        self._events_generated += len(local_events)
        self._current_tick = None

    async def _tick_agent(
        self, agent_id: str, assignment: TickAssignment
    ) -> dict[str, Any]:
        agent = self._registry.get(agent_id)
        if agent is None:
            return {"success": False, "error": f"Agent {agent_id} not found", "events": []}

        processor = self._agent_processors.get(agent.agent_type)
        if processor is None:
            return {"success": False, "error": f"No processor for {agent.agent_type}", "events": []}

        return await processor.process_tick(agent, assignment)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "worker_id": self._config.worker_id,
            "running": self._running,
            "current_tick": self._current_tick,
            "ticks_processed": self._ticks_processed,
            "events_generated": self._events_generated,
            "errors": self._errors,
            "load": self._load,
        }
