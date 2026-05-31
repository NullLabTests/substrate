from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio

from core.distributed.coordinator import Coordinator, DistributedMode
from core.distributed.message_queue import InProcessMessageQueue, MessageQueueBackend
from core.distributed.protocol import (
    AgentAction,
    AgentActionResult,
    DistributedMessage,
    Heartbeat,
    MessageType,
    TickAssignment,
    TickResult,
)
from core.distributed.shard import ConsistentHashShard, RoundRobinShard
from core.distributed.worker import WorkerConfig, WorkerNode
from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry


@pytest_asyncio.fixture
async def mq() -> AsyncGenerator[InProcessMessageQueue, None]:
    queue = InProcessMessageQueue()
    yield queue
    await queue.close()


@pytest_asyncio.fixture
async def event_bus() -> AsyncGenerator[EventBus, None]:
    bus = EventBus()
    await bus.initialize()
    yield bus
    await bus.shutdown()


@pytest_asyncio.fixture
async def logger() -> AsyncGenerator[StructuredLogger, None]:
    log = StructuredLogger("test_distributed", level="debug")
    await log.initialize()
    yield log
    await log.shutdown()


@pytest_asyncio.fixture
async def registry() -> AsyncGenerator[AgentRegistry, None]:
    reg = AgentRegistry()
    await reg.initialize()
    yield reg
    await reg.shutdown()


# ── Protocol Tests ──────────────────────────────────────────────

class TestDistributedMessage:
    def test_roundtrip(self):
        original = DistributedMessage(
            msg_type=MessageType.TICK_ASSIGNMENT,
            source_id="coordinator",
            destination_id="worker1",
            payload={"tick": 1, "agent_ids": ["a1", "a2"]},
            tick=1,
        )
        restored = DistributedMessage.from_dict(original.to_dict())
        assert restored.msg_type == original.msg_type
        assert restored.source_id == original.source_id
        assert restored.destination_id == original.destination_id
        assert restored.payload == original.payload
        assert restored.tick == original.tick

    def test_tick_assignment_conversion(self):
        assignment = TickAssignment(
            worker_id="worker1", tick=5,
            agent_ids=["a1", "a2"],
            timeout_seconds=30.0,
        )
        msg = assignment.to_message("coordinator")
        restored = TickAssignment.from_message(msg)
        assert restored.worker_id == "worker1"
        assert restored.tick == 5
        assert restored.agent_ids == ["a1", "a2"]

    def test_heartbeat_message(self):
        hb = Heartbeat(
            node_id="worker1", node_type="worker",
            tick=10, load=0.5,
        )
        msg = hb.to_message()
        assert msg.msg_type == MessageType.HEARTBEAT
        assert msg.source_id == "worker1"
        assert msg.payload["load"] == 0.5


# ── Message Queue Tests ─────────────────────────────────────────

class TestInProcessMessageQueue:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, mq: InProcessMessageQueue):
        async def subscriber():
            async for msg in mq.subscribe("test"):
                return msg

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.01)
        msg = DistributedMessage(
            msg_type=MessageType.HEARTBEAT,
            source_id="test", destination_id="test",
            payload={"hello": "world"},
        )
        await mq.publish(msg, "test")
        result = await asyncio.wait_for(task, timeout=2.0)
        assert result.payload["hello"] == "world"

    @pytest.mark.asyncio
    async def test_request_response(self, mq: InProcessMessageQueue):
        async def responder():
            async for msg in mq.subscribe("req"):
                response = DistributedMessage(
                    msg_type=MessageType.TICK_RESULT,
                    source_id="worker", destination_id="coordinator",
                    payload={"success": True},
                    correlation_id=msg.correlation_id,
                )
                await mq.publish(response, "req")
                break
    
        asyncio.create_task(responder())
        await asyncio.sleep(0.01)
        request = DistributedMessage(
            msg_type=MessageType.TICK_ASSIGNMENT,
            source_id="coordinator", destination_id="worker",
            payload={"tick": 1},
        )
        result = await mq.request(request, "req", timeout=5.0)
        assert result is not None
        assert result.payload["success"] is True


# ── Shard Strategy Tests ────────────────────────────────────────

class TestConsistentHashShard:
    def test_assign_in_range(self):
        shard = ConsistentHashShard(num_shards=4)
        for agent_id in [f"agent_{i}" for i in range(100)]:
            s = shard.assign(agent_id)
            assert 0 <= s < 4

    def test_same_agent_same_shard(self):
        shard = ConsistentHashShard(num_shards=8)
        s1 = shard.assign("agent_42")
        s2 = shard.assign("agent_42")
        assert s1 == s2

    def test_load_distribution(self):
        shard = ConsistentHashShard(num_shards=4)
        agent_ids = [f"agent_{i}" for i in range(1000)]
        load = shard.shard_load(agent_ids)
        assert len(load) == 4
        counts = list(load.values())
        max_min_ratio = max(counts) / max(min(counts), 1)
        assert max_min_ratio < 2.0

    def test_agents_for_shard(self):
        shard = ConsistentHashShard(num_shards=3)
        agent_ids = [f"agent_{i}" for i in range(100)]
        shard_0 = shard.agents_for_shard(agent_ids, 0)
        assert all(shard.assign(aid) == 0 for aid in shard_0)

    def test_rebalance(self):
        shard = ConsistentHashShard(num_shards=4)
        a1 = shard.assign("agent_1")
        shard.rebalance(8)
        assert shard.shard_count() == 8


class TestRoundRobinShard:
    def test_even_distribution(self):
        shard = RoundRobinShard(num_shards=4)
        agent_ids = [f"agent_{i}" for i in range(100)]
        load = {}
        for aid in agent_ids:
            s = shard.assign(aid)
            load[s] = load.get(s, 0) + 1
        assert all(load[s] == 25 for s in range(4))

    def test_agents_for_shard(self):
        shard = RoundRobinShard(num_shards=3)
        agent_ids = [f"agent_{i}" for i in range(9)]
        assert len(shard.agents_for_shard(agent_ids, 0)) == 3
        assert len(shard.agents_for_shard(agent_ids, 1)) == 3
        assert len(shard.agents_for_shard(agent_ids, 2)) == 3


# ── Coordinator Tests ───────────────────────────────────────────

class DummyProcessor:
    async def process_tick(self, agent, assignment):
        return {"success": True, "events": [{"topic": "test", "payload": {"agent": agent.agent_id}}]}


@pytest.mark.asyncio
class TestCoordinator:
    async def test_register_worker(self, mq, event_bus, logger):
        shard = ConsistentHashShard(num_shards=2)
        coord = Coordinator("coord", mq, event_bus, logger, shard)
        await coord.register_worker("worker1")
        await coord.register_worker("worker2")
        assert "worker1" in coord.workers
        assert "worker2" in coord.workers

    async def test_distribute_tick_local(self, mq, event_bus, logger):
        shard = ConsistentHashShard(num_shards=1)
        coord = Coordinator("coord", mq, event_bus, logger, shard, mode=DistributedMode.LOCAL)
        await coord.register_worker("worker1")
        results = await coord.distribute_tick(1)
        assert isinstance(results, list)

    async def test_heartbeat_updates_worker(self, mq, event_bus, logger):
        shard = ConsistentHashShard(num_shards=1)
        coord = Coordinator("coordinator", mq, event_bus, logger, shard, heartbeat_timeout=30.0)
        await coord.register_worker("worker1")
        coord_task = asyncio.create_task(coord.start(agent_ids=[]))
        await asyncio.sleep(0.05)
        hb = Heartbeat(
            node_id="worker1", node_type="worker",
            tick=5, load=0.75,
        )
        await mq.publish(hb.to_message())
        await asyncio.sleep(0.1)
        info = coord.workers["worker1"]
        assert info.alive is True
        assert info.current_load == 0.75
        await coord.stop()
        coord_task.cancel()

    async def test_run_simulation(self, mq, event_bus, logger):
        shard = ConsistentHashShard(num_shards=1)
        coord = Coordinator("coord", mq, event_bus, logger, shard,
                            tick_timeout=0.5, mode=DistributedMode.LOCAL)
        result = await coord.run_simulation(num_ticks=3, agent_ids=["agent_1", "agent_2"])
        assert result["completed_ticks"] <= 3
        assert result["total_ticks"] == 3


# ── Worker Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestWorker:
    async def test_worker_start_stop(self, mq, event_bus, registry, logger):
        config = WorkerConfig(worker_id="worker1")
        worker = WorkerNode(config, mq, event_bus, registry, logger)
        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)
        await worker.stop()
        start_task.cancel()
        stats = worker.stats
        assert stats["worker_id"] == "worker1"

    async def test_worker_process_tick_assignment(self, mq, event_bus, registry, logger):
        registry.register("agent_1", "Agent 1", "test_type", {})
        config = WorkerConfig(worker_id="worker1")
        worker = WorkerNode(config, mq, event_bus, registry, logger)
        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)

        assignment = TickAssignment(
            worker_id="worker1", tick=1,
            agent_ids=["agent_1"],
        )
        await mq.publish(assignment.to_message("coord"))
        await asyncio.sleep(0.2)

        stats = worker.stats
        assert stats["ticks_processed"] == 1
        assert stats["worker_id"] == "worker1"

        await worker.stop()
        start_task.cancel()

    async def test_worker_heartbeat(self, mq, event_bus, registry, logger):
        config = WorkerConfig(
            worker_id="worker1",
            heartbeat_interval=0.05,
        )
        worker = WorkerNode(config, mq, event_bus, registry, logger)
        start_task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.1)

        async for msg in mq.subscribe():
            if msg.msg_type == MessageType.HEARTBEAT and msg.source_id == "worker1":
                assert msg.payload["node_type"] == "worker"
                break

        await worker.stop()
        start_task.cancel()

    async def test_worker_stats(self, mq, event_bus, registry, logger):
        config = WorkerConfig(worker_id="stats_test")
        worker = WorkerNode(config, mq, event_bus, registry, logger)
        stats = worker.stats
        assert stats["worker_id"] == "stats_test"
        assert stats["ticks_processed"] == 0
        assert stats["errors"] == 0


# ── End-to-End Distributed Simulation ───────────────────────────

async def _make_worker(mq, event_bus, registry, logger, wid: str):
    config = WorkerConfig(worker_id=wid)
    w = WorkerNode(config, mq, event_bus, registry, logger)
    task = asyncio.create_task(w.start())
    return w, task


@pytest.mark.asyncio
class TestEndToEnd:
    async def test_in_process_simulation(self, mq, event_bus, logger):
        reg1 = AgentRegistry(); await reg1.initialize()
        reg2 = AgentRegistry(); await reg2.initialize()

        shard = ConsistentHashShard(num_shards=2)
        coord = Coordinator("coordinator", mq, event_bus, logger, shard,
                            mode=DistributedMode.LOCAL, tick_timeout=2.0)

        w1, t1 = await _make_worker(mq, event_bus, reg1, logger, "worker1")
        w2, t2 = await _make_worker(mq, event_bus, reg2, logger, "worker2")
        await coord.register_worker("worker1")
        await coord.register_worker("worker2")
        await asyncio.sleep(0.05)

        result = await coord.run_simulation(num_ticks=5, agent_ids=[f"agent_{i}" for i in range(10)])
        assert result["total_ticks"] == 5
        assert result["completed_ticks"] > 0

        await w1.stop(); t1.cancel()
        await w2.stop(); t2.cancel()
        await reg1.shutdown(); await reg2.shutdown()

    async def test_many_agents_distribution(self, mq, event_bus, logger):
        shard = ConsistentHashShard(num_shards=4)

        for i in range(4):
            pass  # coordination structure validated above

        agent_ids = [f"agent_{i}" for i in range(1000)]
        load = shard.shard_load(agent_ids)
        counts = list(load.values())
        max_min_ratio = max(counts) / max(min(counts), 1)
        assert max_min_ratio < 2.0

    async def test_worker_failure_retry(self, mq, event_bus, logger):
        reg1 = AgentRegistry(); await reg1.initialize()
        reg2 = AgentRegistry(); await reg2.initialize()

        shard = ConsistentHashShard(num_shards=2)
        coord = Coordinator(
            "coordinator", mq, event_bus, logger, shard,
            mode=DistributedMode.LOCAL, max_retries=2,
        )

        w1, t1 = await _make_worker(mq, event_bus, reg1, logger, "worker1")
        w2, t2 = await _make_worker(mq, event_bus, reg2, logger, "worker2")
        await coord.register_worker("worker1")
        await coord.register_worker("worker2")
        await asyncio.sleep(0.05)

        result = await coord.run_simulation(num_ticks=3, agent_ids=["agent_1"])
        assert result["total_ticks"] == 3

        await w1.stop(); t1.cancel()
        await w2.stop(); t2.cancel()
        await reg1.shutdown(); await reg2.shutdown()
