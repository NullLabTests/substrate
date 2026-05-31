from __future__ import annotations
from typing import Any

from core.events import bus


class EnergySystem:
    def __init__(self, initial_balance: float = 100.0) -> None:
        self._balances: dict[str, float] = {}
        self._initial_balance: float = initial_balance

    def register_agent(self, agent_id: str) -> None:
        self._balances[agent_id] = self._initial_balance
        bus.emit("energy.register", agent_id, {
            "balance": self._initial_balance,
        })

    def get_balance(self, agent_id: str) -> float:
        return self._balances.get(agent_id, 0.0)

    def add(self, agent_id: str, amount: float) -> float:
        old = self._balances.get(agent_id, 0.0)
        self._balances[agent_id] = old + amount
        bus.emit("energy.add", agent_id, {
            "amount": amount,
            "old_balance": old,
            "new_balance": self._balances[agent_id],
        })
        return self._balances[agent_id]

    def spend(self, agent_id: str, amount: float) -> bool:
        old = self._balances.get(agent_id, 0.0)
        if old < amount:
            bus.emit("energy.spend.failed", agent_id, {
                "amount": amount,
                "balance": old,
                "reason": "insufficient",
            })
            return False
        self._balances[agent_id] = old - amount
        bus.emit("energy.spend", agent_id, {
            "amount": amount,
            "old_balance": old,
            "new_balance": self._balances[agent_id],
        })
        return True

    def transfer(self, from_id: str, to_id: str, amount: float) -> bool:
        if self.spend(from_id, amount):
            self.add(to_id, amount)
            bus.emit("energy.transfer", from_id, {
                "from": from_id,
                "to": to_id,
                "amount": amount,
            })
            return True
        return False

    def get_all_balances(self) -> dict[str, float]:
        return dict(self._balances)
