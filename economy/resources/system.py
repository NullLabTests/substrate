from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


@dataclass
class Resource:
    id: str = field(default_factory=_new_id)
    type: str = ""
    quantity: float = 100.0
    regen_rate: float = 1.0
    location: tuple[int, int] = (0, 0)
    max_quantity: float = 100.0


class ResourceSystem:
    def __init__(self) -> None:
        self._resources: dict[str, Resource] = {}

    def register_resource(self, resource: Resource) -> str:
        self._resources[resource.id] = resource
        bus.emit("resource.register", None, {
            "resource_id": resource.id,
            "type": resource.type,
            "quantity": resource.quantity,
            "location": list(resource.location),
        })
        return resource.id

    def tick_generation(self) -> dict[str, float]:
        regen: dict[str, float] = {}
        for rid, res in self._resources.items():
            if res.quantity < res.max_quantity:
                added = min(res.regen_rate, res.max_quantity - res.quantity)
                res.quantity += added
                regen[rid] = added
        bus.emit("resource.tick", None, {
            "resources_regened": len(regen),
            "details": regen,
        })
        return regen

    def harvest(self, agent_id: str, resource_id: str, amount: float = 10.0) -> float:
        res = self._resources.get(resource_id)
        if not res:
            bus.emit("resource.harvest.failed", agent_id, {
                "resource_id": resource_id,
                "reason": "not_found",
            })
            return 0.0
        harvested = min(amount, res.quantity)
        res.quantity -= harvested
        bus.emit("resource.harvest", agent_id, {
            "resource_id": resource_id,
            "type": res.type,
            "harvested": harvested,
            "remaining": res.quantity,
        })
        return harvested

    def get_available(self) -> list[Resource]:
        return [r for r in self._resources.values() if r.quantity > 0]

    def get_resource(self, resource_id: str) -> Resource | None:
        return self._resources.get(resource_id)

    def remove_resource(self, resource_id: str) -> Resource | None:
        return self._resources.pop(resource_id, None)
