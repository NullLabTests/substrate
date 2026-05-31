from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


@dataclass
class Tool:
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    creator_id: str = ""
    created_at: float = field(default_factory=time.time)
    adoption_count: int = 0
    effect: dict[str, Any] = field(default_factory=dict)


class ToolCreationSystem:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def create_tool(
        self,
        creator_id: str,
        name: str,
        description: str,
        effect: dict[str, Any] | None = None,
    ) -> Tool:
        tool = Tool(
            name=name,
            description=description,
            creator_id=creator_id,
            effect=effect or {},
        )
        self._tools[tool.id] = tool
        bus.emit("tool.created", creator_id, {
            "tool_id": tool.id,
            "name": name,
            "description": description,
        })
        return tool

    def get_available_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tools_by_creator(self, agent_id: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.creator_id == agent_id]

    def get_tool(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def increment_adoption(self, tool_id: str) -> None:
        tool = self._tools.get(tool_id)
        if tool:
            tool.adoption_count += 1

    def remove_tool(self, tool_id: str) -> Tool | None:
        return self._tools.pop(tool_id, None)
