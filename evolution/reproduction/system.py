from __future__ import annotations
import math
from typing import Any

from core.events import bus
from civilization.agent.agent import Agent, AgentStatus
from ..mutation.system import MutationSystem


class ReproductionSystem:
    def __init__(
        self,
        mutation_system: MutationSystem | None = None,
        min_energy: float = 50.0,
        energy_cost: float = 30.0,
    ) -> None:
        self._mutation_system = mutation_system or MutationSystem()
        self._min_energy: float = min_energy
        self._energy_cost: float = energy_cost
        self._parent_child: dict[str, list[str]] = {}
        self._child_parent: dict[str, list[str]] = {}

    def can_reproduce(self, agent_id: str, world_agents: dict[str, Agent]) -> bool:
        agent = world_agents.get(agent_id)
        if not agent or agent.status == AgentStatus.DEAD:
            return False
        return agent.energy >= self._min_energy

    def reproduce(
        self,
        parent_id: str,
        partner_id: str | None = None,
        world_agents: dict[str, Agent] | None = None,
    ) -> Agent | None:
        parent = (world_agents or {}).get(parent_id)
        if not parent or not self.can_reproduce(parent_id, world_agents or {}):
            bus.emit("reproduction.failed", parent_id, {
                "reason": "cannot_reproduce",
                "energy": parent.energy if parent else "N/A",
            })
            return None

        partner: Agent | None = None
        if partner_id:
            partner = (world_agents or {}).get(partner_id)
            if not partner or partner.status == AgentStatus.DEAD:
                bus.emit("reproduction.failed", parent_id, {
                    "reason": "partner_invalid",
                    "partner_id": partner_id,
                })
                return None

        child = parent.reproduce()
        if not child:
            return None

        parent_traits = dict(parent.traits)
        if partner:
            partner_traits = dict(partner.traits)
            blended: dict[str, float] = {}
            for key in parent_traits:
                blended[key] = (parent_traits[key] + partner_traits.get(key, parent_traits[key])) / 2.0
            child.traits = blended
        else:
            child.traits = dict(parent.traits)

        mutation_rate = self._mutation_system.get_mutation_rate(parent_id)
        child.traits = self._mutation_system.mutate(child.traits, mutation_rate)

        parent.energy -= self._energy_cost
        if partner:
            partner.energy -= self._energy_cost * 0.5

        parent_ids = [parent_id]
        if partner:
            parent_ids.append(partner_id)
        self._parent_child.setdefault(parent_id, []).append(child.agent_id)
        self._child_parent[child.agent_id] = parent_ids

        bus.emit("reproduction.birth", child.agent_id, {
            "parent_ids": parent_ids,
            "child_id": child.agent_id,
            "traits": child.traits,
            "parent_energy_after": parent.energy,
        })
        return child

    def get_offspring(self, agent_id: str) -> list[str]:
        return self._parent_child.get(agent_id, [])

    def get_parents(self, agent_id: str) -> list[str]:
        return self._child_parent.get(agent_id, [])
