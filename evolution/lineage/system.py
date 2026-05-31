from __future__ import annotations
import time
from typing import Any

from core.events import bus


class LineageSystem:
    def __init__(self) -> None:
        self._parents: dict[str, list[str]] = {}
        self._children: dict[str, list[str]] = {}
        self._generation: dict[str, int] = {}
        self._birth_times: dict[str, float] = {}
        self._death_times: dict[str, float] = {}

    def register_birth(self, child_id: str, parent_ids: list[str]) -> None:
        self._parents[child_id] = parent_ids
        self._birth_times[child_id] = time.time()
        for pid in parent_ids:
            self._children.setdefault(pid, []).append(child_id)

        if parent_ids:
            parent_gens = [
                self._generation.get(pid, 0) for pid in parent_ids
            ]
            child_gen = max(parent_gens) + 1
        else:
            child_gen = 0
        self._generation[child_id] = child_gen

        bus.emit("lineage.birth", child_id, {
            "parent_ids": parent_ids,
            "generation": child_gen,
        })

    def register_death(self, agent_id: str) -> None:
        self._death_times[agent_id] = time.time()
        bus.emit("lineage.death", agent_id, {
            "lifespan": self._death_times[agent_id] - self._birth_times.get(agent_id, self._death_times[agent_id]),
            "generation": self._generation.get(agent_id, 0),
        })

    def get_ancestors(self, agent_id: str, depth: int = 10) -> list[str]:
        ancestors: list[str] = []
        queue: list[tuple[str, int]] = [(agent_id, 0)]
        visited: set[str] = set()
        while queue:
            current, d = queue.pop(0)
            if d >= depth or current in visited:
                continue
            visited.add(current)
            for parent in self._parents.get(current, []):
                ancestors.append(parent)
                queue.append((parent, d + 1))
        return ancestors

    def get_descendants(self, agent_id: str) -> list[str]:
        descendants: list[str] = []
        queue: list[str] = [agent_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for child in self._children.get(current, []):
                descendants.append(child)
                queue.append(child)
        return descendants

    def get_generation(self, agent_id: str) -> int:
        return self._generation.get(agent_id, 0)

    def get_lineage_tree(self, agent_id: str, max_depth: int = 5) -> dict[str, Any]:
        def build(node: str, depth: int) -> dict[str, Any] | None:
            if depth > max_depth:
                return None
            return {
                "agent_id": node,
                "generation": self._generation.get(node, 0),
                "children": [
                    build(c, depth + 1)
                    for c in self._children.get(node, [])
                ],
            }
        return {"root": agent_id, "tree": build(agent_id, 0)}

    def get_lineage_stats(self) -> dict[str, Any]:
        alive = len(self._birth_times) - len(self._death_times)
        return {
            "total_born": len(self._birth_times),
            "total_dead": len(self._death_times),
            "alive": alive,
            "max_generation": max(self._generation.values()) if self._generation else 0,
            "avg_children": (
                sum(len(v) for v in self._children.values()) / len(self._children)
                if self._children else 0.0
            ),
        }
