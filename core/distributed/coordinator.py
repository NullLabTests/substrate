from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.distributed.message_queue import MessageQueueBackend
from core.distributed.protocol import (
    DistributedMessage,
    MessageType,
    TickAssignment,
    TickResult,
)
from core.distributed.shard import ConsistentHashShard
from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.seed import SimulationSeed


class DistributedMode(Enum):
    LOCAL = "local"
    DISTRIBUTED = "distributed"
    HYBRID = "hybrid"


@dataclass
class WorkerInfo:
    worker_id: str
    host: str = "localhost"
    port: int = 0
    last_heartbeat: float = 0.0
    current_load: float = 0.0
    current_tick: int = 0
    alive: bool = True
    assigned_agents: list[str] = field(default_factory=list)
    failed_ticks: int = 0
    total_ticks: int = 0

    @property
    def is_stale(self, timeout: float = 15.0) -> bool:
        return (time.monotonic() - self.last_heartbeat) > timeout


class Coordinator:
    def __init__(
        self,
        coordinator_id: str,
        message_queue: MessageQueueBackend,
        event_bus: EventBus,
        logger: StructuredLogger,
        shard: ConsistentHashShard,
        mode: DistributedMode = DistributedMode.LOCAL,
        seed: SimulationSeed | None = None,
        heartbeat_timeout: float = 15.0,
        tick_timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._coordinator_id = coordinator_id
        self._mq = message_queue
        self._event_bus = event_bus
        self._log = logger
        self._shard = shard
        self._mode = mode
        self._seed = seed
        self._heartbeat_timeout = heartbeat_timeout
        self._tick_timeout = tick_timeout
        self._max_retries = max_retries

        self._workers: dict[str, WorkerInfo] = {}
        self._next_tick: int = 1
        self._pending_ticks: dict[int, TickAssignment] = {}
        self._tick_results: dict[int, list[TickResult]] = {}
        self._full_agent_ids: list[str] = []
        self._running = False
        self._tick_processors: list[Callable[[int], Coroutine[Any, Any, None]]] = []
        self._global_state: dict[str, Any] = {}
        self._total_ticks: int = 0
        self._retries: int = 0
        self._message_loop_task: asyncio.Task[None] | None = None

    @property
    def workers(self) -> dict[str, WorkerInfo]:
        return dict(self._workers)

    @property
    def mode(self) -> DistributedMode:
        return self._mode

    @property
    def shard_strategy(self) -> ConsistentHashShard:
        return self._shard

    def add_tick_processor(
        self, processor: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        self._tick_processors.append(processor)

    async def start(self, agent_ids: list[str] | None = None) -> None:
        self._running = True
        if agent_ids:
            self._full_agent_ids = agent_ids
        self._log.info(
            "coordinator_started",
            coordinator_id=self._coordinator_id,
            mode=self._mode.value,
            agent_count=len(self._full_agent_ids),
            shard_count=self._shard.shard_count(),
        )
        await asyncio.gather(
            self._heartbeat_monitor(),
            self._message_loop(),
        )

    async def stop(self) -> None:
        self._running = False
        if self._message_loop_task:
            self._message_loop_task.cancel()
            try:
                await self._message_loop_task
            except asyncio.CancelledError:
                pass
            self._message_loop_task = None
        shutdown = DistributedMessage(
            msg_type=MessageType.SHUTDOWN,
            source_id=self._coordinator_id,
            destination_id="*",
            payload={},
        )
        await self._mq.publish(shutdown)
        self._log.info("coordinator_stopped", coordinator_id=self._coordinator_id)

    async def _process_tick_locally(self, tick: int, agent_ids: list[str]) -> TickResult:
        results: dict[str, dict[str, Any]] = {}
        for aid in agent_ids:
            results[aid] = {"success": True, "tick": tick, "processed": "local"}
        return TickResult(
            worker_id=self._coordinator_id, tick=tick,
            agent_results=results, local_events=[], success=True,
            duration_ms=0.0,
        )

    async def distribute_tick(self, tick: int) -> list[TickResult]:
        if self._message_loop_task is None:
            self._running = True
            self._message_loop_task = asyncio.create_task(self._message_loop())

        infos = list(self._workers.values())

        if not infos:
            self._log.warning("no_workers_available", tick=tick)
            if self._mode == DistributedMode.LOCAL:
                return [await self._process_tick_locally(tick, self._full_agent_ids)]
            return []

        agent_shards: dict[str, list[str]] = {}
        for info in infos:
            agent_shards[info.worker_id] = self._shard.agents_for_shard(
                self._full_agent_ids,
                self._shard.assign(info.worker_id) % self._shard.shard_count(),
            )
            info.assigned_agents = agent_shards[info.worker_id]
            info.current_tick = tick

        timeout = max(
            self._tick_timeout,
            max(len(aids) for aids in agent_shards.values()) * 0.5,
        )
        assignments: list[TickAssignment] = []
        for worker_id, agent_ids in agent_shards.items():
            if not agent_ids:
                continue
            seed_derivation = None
            if self._seed:
                seed_derivation = self._seed.derive(f"tick_{tick}_{worker_id}")
            assignment = TickAssignment(
                worker_id=worker_id,
                tick=tick,
                agent_ids=agent_ids,
                global_state_snapshot=dict(self._global_state),
                seed_derivation=seed_derivation,
                timeout_seconds=timeout,
            )
            assignments.append(assignment)

        self._pending_ticks[tick] = TickAssignment(
            worker_id="coordinator",
            tick=tick,
            agent_ids=[a.worker_id for a in assignments],
            timeout_seconds=timeout,
        )
        self._tick_results[tick] = []

        for assignment in assignments:
            await self._mq.publish(
                assignment.to_message(self._coordinator_id)
            )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self._tick_results[tick]) >= sum(
                1 for a in assignments if a.agent_ids
            ):
                break
            await asyncio.sleep(0.01)

        results = self._tick_results.pop(tick, [])
        self._pending_ticks.pop(tick, None)

        if not results and self._mode == DistributedMode.LOCAL and self._full_agent_ids:
            results.append(await self._process_tick_locally(tick, self._full_agent_ids))

        return results

    async def run_simulation(
        self,
        num_ticks: int,
        agent_ids: list[str],
        tick_callback: Callable[[int], Coroutine[Any, Any, None]] | None = None,
    ) -> dict[str, Any]:
        self._full_agent_ids = agent_ids
        self._running = True
        self._message_loop_task = asyncio.create_task(self._message_loop())
        self._log.info(
            "simulation_started",
            ticks=num_ticks,
            agents=len(agent_ids),
            shards=self._shard.shard_count(),
        )
        t0 = time.monotonic()
        completed_ticks = 0
        failed_ticks = 0

        for tick in range(1, num_ticks + 1):
            if not self._running:
                break
            self._next_tick = tick
            for processor in self._tick_processors:
                await processor(tick)
            if tick_callback:
                await tick_callback(tick)

            results = await self.distribute_tick(tick)
            all_success = all(r.success for r in results) if results else True
            retries = 0
            while not all_success and retries < self._max_retries:
                self._log.warning("tick_retry", tick=tick, attempt=retries + 1)
                retries += 1
                self._retries += 1
                failed = [r for r in results if not r.success]
                retry_results = await self._retry_failed(tick, failed)
                results.extend(retry_results)
                all_success = all(r.success for r in results) if results else True

            if all_success:
                completed_ticks += 1
            else:
                failed_ticks += 1
                self._log.error("tick_failed_all", tick=tick)

            self._publish_tick_events(results)

        elapsed = time.monotonic() - t0
        self._total_ticks += completed_ticks
        self._running = False
        if self._message_loop_task:
            self._message_loop_task.cancel()
            try:
                await self._message_loop_task
            except asyncio.CancelledError:
                pass
            self._message_loop_task = None
        self._log.info(
            "simulation_completed",
            completed=completed_ticks,
            failed=failed_ticks,
            elapsed_seconds=round(elapsed, 2),
        )
        return {
            "completed_ticks": completed_ticks,
            "failed_ticks": failed_ticks,
            "total_ticks": num_ticks,
            "elapsed_seconds": elapsed,
            "workers": {wid: wi.total_ticks for wid, wi in self._workers.items()},
            "retries": self._retries,
        }

    async def _retry_failed(
        self, tick: int, failed_results: list[TickResult]
    ) -> list[TickResult]:
        failed_worker_ids = [r.worker_id for r in failed_results]
        alt_workers = [
            w for w in self._workers if w not in failed_worker_ids
        ]
        if not alt_workers:
            return failed_results
        agent_ids = []
        for r in failed_results:
            agent_ids.extend(r.agent_results.keys())
        alt_worker = alt_workers[0]
        retry_assignment = TickAssignment(
            worker_id=alt_worker,
            tick=tick,
            agent_ids=agent_ids,
            timeout_seconds=self._tick_timeout,
        )
        await self._mq.publish(
            retry_assignment.to_message(self._coordinator_id)
        )
        await asyncio.sleep(self._tick_timeout * 0.5)
        return self._tick_results.pop(tick, [])

    def _publish_tick_events(self, results: list[TickResult]) -> None:
        for result in results:
            for event_data in result.local_events:
                if isinstance(event_data, dict):
                    self._event_bus.publish_raw(event_data)

    async def register_worker(self, worker_id: str, host: str = "localhost", port: int = 0) -> None:
        if worker_id not in self._workers:
            self._workers[worker_id] = WorkerInfo(
                worker_id=worker_id, host=host, port=port,
            )
            self._log.info("worker_registered", worker_id=worker_id)

    async def _heartbeat_monitor(self) -> None:
        while self._running:
            now = time.monotonic()
            stale = [
                wid for wid, info in self._workers.items()
                if info.is_stale(self._heartbeat_timeout)
            ]
            for wid in stale:
                self._workers[wid].alive = False
                self._log.warning("worker_stale", worker_id=wid)
            await asyncio.sleep(self._heartbeat_timeout * 0.5)

    async def _message_loop(self) -> None:
        async for msg in self._mq.subscribe():
            if not self._running:
                break
            if msg.destination_id not in (self._coordinator_id, "*", ""):
                continue
            try:
                await self._handle_message(msg)
            except Exception as exc:
                self._log.error(
                    "coordinator_message_error",
                    msg_type=msg.msg_type.value,
                    error=str(exc),
                )

    async def _handle_message(self, msg: DistributedMessage) -> None:
        if msg.msg_type == MessageType.HEARTBEAT:
            if msg.source_id not in self._workers:
                await self.register_worker(msg.source_id)
            info = self._workers[msg.source_id]
            info.last_heartbeat = time.monotonic()
            info.current_load = msg.payload.get("load", 0.0)
            info.current_tick = msg.payload.get("tick", 0)
            info.alive = True
            info.total_ticks += 1
        elif msg.msg_type == MessageType.TICK_RESULT:
            result = TickResult(
                worker_id=msg.source_id,
                tick=msg.payload["tick"],
                agent_results=msg.payload.get("agent_results", {}),
                local_events=msg.payload.get("local_events", []),
                success=msg.payload.get("success", False),
                error=msg.payload.get("error"),
                duration_ms=msg.payload.get("duration_ms", 0.0),
            )
            tick = result.tick
            if tick in self._tick_results:
                self._tick_results[tick].append(result)
        elif msg.msg_type == MessageType.REGISTER_WORKER:
            await self.register_worker(
                msg.source_id,
                host=msg.payload.get("host", "localhost"),
                port=msg.payload.get("port", 0),
            )
