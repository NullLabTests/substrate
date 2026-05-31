from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SimulationSeed:
    seed: int
    created_at: str
    label: str | None = None

    def derive(self, namespace: str) -> int:
        h = hashlib.sha256(f"{self.seed}:{namespace}".encode()).hexdigest()
        return int(h[:16], 16)

    def to_dict(self) -> dict[str, Any]:
        return {"seed": self.seed, "created_at": self.created_at, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationSeed:
        return cls(
            seed=data["seed"],
            created_at=data.get("created_at", ""),
            label=data.get("label"),
        )

    @classmethod
    def generate(cls, label: str | None = None) -> SimulationSeed:
        return cls(
            seed=random.SystemRandom().randint(0, 2**63 - 1),
            created_at=datetime.now(UTC).isoformat(),
            label=label,
        )


class SeededContext:
    def __init__(self, master_seed: SimulationSeed, namespace: str) -> None:
        self._rng = random.Random(master_seed.derive(namespace))

    def __enter__(self) -> random.Random:
        return self._rng

    def __exit__(self, *args: Any) -> None:
        pass
