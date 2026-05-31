from __future__ import annotations
import secrets
import time
from typing import Any

from core.events import bus
from ..agent.agent import Agent, AgentStatus


def _new_id() -> str:
    return secrets.token_hex(16)


class World:
    def __init__(self, world_id: str | None = None) -> None:
        self.world_id: str = world_id or _new_id()
        self.agents: dict[str, Agent] = {}
        self.tick_count: int = 0
        self.rules: dict[str, Any] = {
            "max_population": 100,
            "energy_decay_per_tick": 1.0,
            "enable_reproduction": True,
        }
        self._started_at: float = time.time()

        bus.emit("world.spawn", None, {
            "world_id": self.world_id,
            "rules": self.rules,
        })

    def step(self) -> dict[str, Any]:
        self.tick_count += 1
        dead_agents: list[str] = []
        state_snapshot: dict[str, Any] = {
            "tick": self.tick_count,
            "agent_count": len(self.agents),
            "agents": {},
        }

        for agent_id, agent in self.agents.items():
            if agent.status == AgentStatus.DEAD:
                dead_agents.append(agent_id)
                continue
            agent.act(self.tick_count)
            state_snapshot["agents"][agent_id] = {
                "energy": agent.energy,
                "position": list(agent.position),
                "status": agent.status.value,
            }

        for agent_id in dead_agents:
            self.remove_agent(agent_id)

        self.apply_rules()
        bus.emit("world.step", None, state_snapshot)
        return state_snapshot

    def add_agent(self, agent: Agent) -> str:
        self.agents[agent.agent_id] = agent
        bus.emit("world.add_agent", agent.agent_id, {
            "world_id": self.world_id,
            "tick": self.tick_count,
        })
        return agent.agent_id

    def remove_agent(self, agent_id: str) -> Agent | None:
        agent = self.agents.pop(agent_id, None)
        if agent:
            bus.emit("world.remove_agent", agent_id, {
                "world_id": self.world_id,
                "tick": self.tick_count,
            })
        return agent

    def get_state(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "tick": self.tick_count,
            "agent_count": len(self.agents),
            "agents": {
                aid: {
                    "energy": a.energy,
                    "position": list(a.position),
                    "status": a.status.value,
                    "traits": a.traits,
                }
                for aid, a in self.agents.items()
            },
            "rules": self.rules,
            "uptime": time.time() - self._started_at,
        }

    def apply_rules(self) -> None:
        for agent in list(self.agents.values()):
            agent.energy -= self.rules["energy_decay_per_tick"]
            if agent.energy <= 0:
                agent.die()

    def get_agent(self, agent_id: str) -> Agent | None:
        return self.agents.get(agent_id)

    def __repr__(self) -> str:
        return f"World(id={self.world_id[:8]}, tick={self.tick_count}, agents={len(self.agents)})"
