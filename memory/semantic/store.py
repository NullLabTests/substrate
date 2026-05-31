from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


@dataclass
class Fact:
    id: str = field(default_factory=_new_id)
    concept: str = ""
    relation: str = ""
    target: str = ""
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)


class SemanticMemory:
    def __init__(self) -> None:
        self._store: dict[str, list[Fact]] = {}
        self._inheritance_graph: dict[str, list[str]] = {}

    def store_fact(self, agent_id: str, fact: Fact) -> None:
        self._store.setdefault(agent_id, []).append(fact)
        bus.emit("memory.semantic.store", agent_id, {
            "fact_id": fact.id,
            "concept": fact.concept,
            "relation": fact.relation,
            "confidence": fact.confidence,
        })

    def query(
        self, agent_id: str, concept: str
    ) -> list[Fact]:
        results: list[Fact] = []
        visited: set[str] = set()
        queue: list[str] = [agent_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for fact in self._store.get(current, []):
                if fact.concept == concept:
                    results.append(fact)
            queue.extend(self._inheritance_graph.get(current, []))
        bus.emit("memory.semantic.query", agent_id, {
            "concept": concept,
            "results": len(results),
        })
        return results

    def merge(self, agent_id: str, facts: list[Fact]) -> int:
        count = 0
        for fact in facts:
            existing = self._store.get(agent_id, [])
            matched = any(
                f.concept == fact.concept and f.relation == fact.relation
                for f in existing
            )
            if matched:
                for f in existing:
                    if f.concept == fact.concept and f.relation == fact.relation:
                        f.confidence = max(f.confidence, fact.confidence)
                        f.target = fact.target
                        break
            else:
                self._store.setdefault(agent_id, []).append(fact)
            count += 1
        bus.emit("memory.semantic.merge", agent_id, {
            "merged": count,
        })
        return count

    def inherit(self, child_id: str, parent_id: str) -> None:
        self._inheritance_graph.setdefault(child_id, []).append(parent_id)
        bus.emit("memory.semantic.inherit", child_id, {
            "parent_id": parent_id,
        })

    def get_all_facts(self, agent_id: str) -> list[Fact]:
        return self._store.get(agent_id, [])

    def clear_agent(self, agent_id: str) -> None:
        self._store.pop(agent_id, None)
        self._inheritance_graph.pop(agent_id, None)
