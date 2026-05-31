from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


class TradeStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class TradeProposal:
    id: str = field(default_factory=_new_id)
    from_agent: str = ""
    to_agent: str = ""
    offer: dict[str, float] = field(default_factory=dict)
    request: dict[str, float] = field(default_factory=dict)
    status: TradeStatus = TradeStatus.PENDING
    created_at: float = field(default_factory=time.time)


class TradeSystem:
    def __init__(self) -> None:
        self._trades: dict[str, TradeProposal] = {}
        self._trade_history: list[TradeProposal] = []

    def propose_trade(
        self,
        from_agent: str,
        to_agent: str,
        offer: dict[str, float],
        request: dict[str, float],
    ) -> TradeProposal:
        trade = TradeProposal(
            from_agent=from_agent,
            to_agent=to_agent,
            offer=offer,
            request=request,
        )
        self._trades[trade.id] = trade
        bus.emit("trade.propose", from_agent, {
            "trade_id": trade.id,
            "to_agent": to_agent,
            "offer": offer,
            "request": request,
        })
        return trade

    def accept_trade(self, trade_id: str) -> bool:
        trade = self._trades.get(trade_id)
        if not trade or trade.status != TradeStatus.PENDING:
            return False
        trade.status = TradeStatus.ACCEPTED
        self._trade_history.append(trade)
        del self._trades[trade_id]
        bus.emit("trade.accept", trade.from_agent, {
            "trade_id": trade_id,
            "from": trade.from_agent,
            "to": trade.to_agent,
            "offer": trade.offer,
            "request": trade.request,
        })
        return True

    def reject_trade(self, trade_id: str) -> bool:
        trade = self._trades.get(trade_id)
        if not trade or trade.status != TradeStatus.PENDING:
            return False
        trade.status = TradeStatus.REJECTED
        self._trade_history.append(trade)
        del self._trades[trade_id]
        bus.emit("trade.reject", trade.from_agent, {
            "trade_id": trade_id,
        })
        return True

    def get_active_trades(self) -> list[TradeProposal]:
        return list(self._trades.values())

    def get_trade_history(
        self, agent_id: str | None = None, limit: int = 100
    ) -> list[TradeProposal]:
        if agent_id is None:
            return self._trade_history[-limit:]
        return [
            t for t in self._trade_history
            if t.from_agent == agent_id or t.to_agent == agent_id
        ][-limit:]
