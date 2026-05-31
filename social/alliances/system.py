from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


@dataclass
class Alliance:
    id: str = field(default_factory=_new_id)
    members: set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    dissolved_at: float | None = None


class AllianceSystem:
    def __init__(self) -> None:
        self._alliances: dict[str, Alliance] = {}
        self._agent_alliances: dict[str, set[str]] = {}

    def propose_alliance(self, agent_a: str, agent_b: str) -> str:
        existing_a = self._agent_alliances.get(agent_a, set())
        existing_b = self._agent_alliances.get(agent_b, set())
        common = existing_a & existing_b
        for alliance_id in common:
            alliance = self._alliances.get(alliance_id)
            if alliance and alliance.dissolved_at is None:
                bus.emit("alliance.propose.duplicate", agent_a, {
                    "agent_b": agent_b,
                    "existing_alliance": alliance_id,
                })
                return alliance_id

        alliance = Alliance(members={agent_a, agent_b})
        self._alliances[alliance.id] = alliance
        self._agent_alliances.setdefault(agent_a, set()).add(alliance.id)
        self._agent_alliances.setdefault(agent_b, set()).add(alliance.id)
        bus.emit("alliance.propose", agent_a, {
            "alliance_id": alliance.id,
            "partner": agent_b,
        })
        return alliance.id

    def join(self, alliance_id: str, agent_id: str) -> bool:
        alliance = self._alliances.get(alliance_id)
        if not alliance or alliance.dissolved_at is not None:
            return False
        alliance.members.add(agent_id)
        self._agent_alliances.setdefault(agent_id, set()).add(alliance_id)
        bus.emit("alliance.join", agent_id, {
            "alliance_id": alliance_id,
        })
        return True

    def leave(self, alliance_id: str, agent_id: str) -> bool:
        alliance = self._alliances.get(alliance_id)
        if not alliance or alliance.dissolved_at is not None:
            return False
        alliance.members.discard(agent_id)
        if agent_id in self._agent_alliances:
            self._agent_alliances[agent_id].discard(alliance_id)
        bus.emit("alliance.leave", agent_id, {
            "alliance_id": alliance_id,
        })
        if len(alliance.members) < 2:
            self.dissolve(alliance_id)
        return True

    def dissolve(self, alliance_id: str) -> bool:
        alliance = self._alliances.get(alliance_id)
        if not alliance or alliance.dissolved_at is not None:
            return False
        alliance.dissolved_at = time.time()
        for member in alliance.members:
            if member in self._agent_alliances:
                self._agent_alliances[member].discard(alliance_id)
        bus.emit("alliance.dissolve", None, {
            "alliance_id": alliance_id,
            "member_count": len(alliance.members),
            "lifespan": alliance.dissolved_at - alliance.created_at,
        })
        return True

    def get_alliance_members(self, alliance_id: str) -> list[str]:
        alliance = self._alliances.get(alliance_id)
        if not alliance or alliance.dissolved_at is not None:
            return []
        return list(alliance.members)

    def get_agent_alliances(self, agent_id: str) -> list[Alliance]:
        alliance_ids = self._agent_alliances.get(agent_id, set())
        return [self._alliances[aid] for aid in alliance_ids if aid in self._alliances]

    def get_active_alliances(self) -> list[Alliance]:
        return [a for a in self._alliances.values() if a.dissolved_at is None]
