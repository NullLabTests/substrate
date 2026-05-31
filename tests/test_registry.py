"""Tests for AgentRegistry."""

from __future__ import annotations

import pytest

from core.registry.agent_registry import AgentRegistry, AgentStatus


class TestAgentRegistry:
    async def test_register_and_get(self, registry: AgentRegistry) -> None:
        meta = registry.register("agent-1", "Alpha", "worker")
        assert meta.id == "agent-1"
        assert meta.name == "Alpha"
        assert meta.agent_type == "worker"
        assert meta.status == AgentStatus.CREATED

        fetched = registry.get("agent-1")
        assert fetched is not None
        assert fetched.id == "agent-1"

    async def test_register_duplicate_raises(self, registry: AgentRegistry) -> None:
        registry.register("dup", "Dup", "worker")
        with pytest.raises(ValueError, match="already registered"):
            registry.register("dup", "Dup2", "worker")

    async def test_unregister(self, registry: AgentRegistry) -> None:
        registry.register("agent-2", "Beta", "coordinator")
        removed = registry.unregister("agent-2")
        assert removed is not None
        assert registry.get("agent-2") is None

    async def test_set_status(self, registry: AgentRegistry) -> None:
        registry.register("agent-3", "Gamma", "worker")
        meta = registry.set_status("agent-3", AgentStatus.ACTIVE)
        assert meta is not None
        assert meta.status == AgentStatus.ACTIVE

    async def test_heartbeat(self, registry: AgentRegistry) -> None:
        registry.register("agent-4", "Delta", "worker")
        result = await registry.heartbeat("agent-4")
        assert result is True
        result = await registry.heartbeat("nonexistent")
        assert result is False

    async def test_list_agents(self, registry: AgentRegistry) -> None:
        registry.register("a1", "One", "worker")
        registry.register("a2", "Two", "coordinator")
        registry.register("a3", "Three", "worker")
        registry.set_status("a3", AgentStatus.ACTIVE)

        all_agents = registry.list_agents()
        assert len(all_agents) == 3

        workers = registry.list_agents(agent_type="worker")
        assert len(workers) == 2

        active = registry.list_agents(status=AgentStatus.ACTIVE)
        assert len(active) == 1

    async def test_count(self, registry: AgentRegistry) -> None:
        assert registry.count == 0
        registry.register("c1", "One", "worker")
        assert registry.count == 1

    async def test_save_and_load_state(self, registry: AgentRegistry) -> None:
        registry.register("s1", "SaveTest", "worker", metadata={"key": "val"})
        state = await registry.save_state()
        assert "s1" in state["agents"]

        new_reg = AgentRegistry()
        await new_reg.load_state(state)
        assert new_reg.count == 1
        assert new_reg.get("s1") is not None
        assert new_reg.get("s1").metadata == {"key": "val"}
