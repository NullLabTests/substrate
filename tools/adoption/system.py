from __future__ import annotations
import time
from typing import Any

from core.events import bus
from ..creation.system import ToolCreationSystem


class ToolAdoptionSystem:
    def __init__(self, creation_system: ToolCreationSystem | None = None) -> None:
        self._creation = creation_system or ToolCreationSystem()
        self._agent_tools: dict[str, set[str]] = {}
        self._adoption_log: list[dict[str, Any]] = []

    def adopt_tool(self, agent_id: str, tool_id: str) -> bool:
        tool = self._creation.get_tool(tool_id)
        if not tool:
            bus.emit("tool.adopt.failed", agent_id, {
                "tool_id": tool_id,
                "reason": "not_found",
            })
            return False
        self._agent_tools.setdefault(agent_id, set()).add(tool_id)
        self._creation.increment_adoption(tool_id)
        entry = {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "action": "adopt",
            "timestamp": time.time(),
        }
        self._adoption_log.append(entry)
        bus.emit("tool.adopt", agent_id, {
            "tool_id": tool_id,
            "tool_name": tool.name,
        })
        return True

    def abandon_tool(self, agent_id: str, tool_id: str) -> bool:
        if agent_id not in self._agent_tools or tool_id not in self._agent_tools[agent_id]:
            return False
        self._agent_tools[agent_id].discard(tool_id)
        entry = {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "action": "abandon",
            "timestamp": time.time(),
        }
        self._adoption_log.append(entry)
        bus.emit("tool.abandon", agent_id, {
            "tool_id": tool_id,
        })
        return True

    def share_tool(self, from_id: str, to_id: str, tool_id: str) -> bool:
        if from_id not in self._agent_tools or tool_id not in self._agent_tools[from_id]:
            bus.emit("tool.share.failed", from_id, {
                "tool_id": tool_id,
                "to_id": to_id,
                "reason": "sender_does_not_own",
            })
            return False
        self.adopt_tool(to_id, tool_id)
        bus.emit("tool.share", from_id, {
            "tool_id": tool_id,
            "to_id": to_id,
        })
        return True

    def get_adopted_tools(self, agent_id: str) -> list[str]:
        return list(self._agent_tools.get(agent_id, set()))

    def get_tool_adoption_rate(self, tool_id: str) -> float:
        tool = self._creation.get_tool(tool_id)
        if not tool:
            return 0.0
        total_agents = len(self._agent_tools)
        if total_agents == 0:
            return 0.0
        adopters = sum(1 for tools in self._agent_tools.values() if tool_id in tools)
        return adopters / total_agents

    def get_all_adoptions(self) -> dict[str, list[str]]:
        return {aid: list(tools) for aid, tools in self._agent_tools.items()}

    def get_adoption_log(
        self, agent_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if agent_id is None:
            return self._adoption_log[-limit:]
        return [e for e in self._adoption_log if e["agent_id"] == agent_id][-limit:]
