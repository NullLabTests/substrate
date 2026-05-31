from __future__ import annotations
import random
from typing import Any

from core.events import bus


class MutationSystem:
    def __init__(self, default_rate: float = 0.1) -> None:
        self._rates: dict[str, float] = {}
        self._default_rate: float = default_rate

    def mutate(self, traits: dict[str, float], rate: float | None = None) -> dict[str, float]:
        mutation_rate = rate if rate is not None else self._default_rate
        result: dict[str, float] = {}
        mutations: dict[str, dict[str, float]] = {}

        for key, value in traits.items():
            if random.random() < mutation_rate:
                delta = random.gauss(0, 0.1)
                new_value = max(0.1, min(3.0, value + delta))
                result[key] = round(new_value, 4)
                mutations[key] = {"old": value, "new": result[key], "delta": delta}
            else:
                result[key] = value

        bus.emit("mutation.apply", None, {
            "traits_mutated": len(mutations),
            "mutations": mutations,
            "rate": mutation_rate,
        })
        return result

    def get_mutation_rate(self, agent_id: str) -> float:
        return self._rates.get(agent_id, self._default_rate)

    def set_mutation_rate(self, agent_id: str, rate: float) -> None:
        rate = max(0.0, min(1.0, rate))
        self._rates[agent_id] = rate
        bus.emit("mutation.rate_set", agent_id, {
            "rate": rate,
        })
