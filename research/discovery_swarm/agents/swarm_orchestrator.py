from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.events.bus import EventPriority, SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


class SwarmOrchestratorAgent(DiscoveryAgent):
    def __init__(
        self,
        name: str = "Swarm Orchestrator",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Swarm Orchestrator",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )
        self._active_missions: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.mission.start", self._on_mission_start)
        self._subscribe("discovery.literature.complete", self._on_literature_complete)
        self._subscribe("discovery.hypothesis.complete", self._on_hypothesis_complete)
        self._subscribe("discovery.critique.complete", self._on_critique_complete)
        self._subscribe("discovery.simulation.complete", self._on_simulation_complete)
        self._subscribe("discovery.uncertainty.complete", self._on_uncertainty_complete)
        self._subscribe("discovery.synthesis.complete", self._on_synthesis_complete)
        self._logger.info("orchestrator_ready", module=self.role)

    async def _on_mission_start(self, event: SystemEvent) -> None:
        question = event.payload.get("research_question", "")
        mission_id = event.payload.get("mission_id", "")
        context = event.payload.get("context", {})
        if not question or not mission_id:
            return

        self._active_missions[mission_id] = {
            "question": question,
            "mission_id": mission_id,
            "phase": "planning",
            "context": context,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store_episode("mission_started", {"mission_id": mission_id, "question": question[:80]}, importance=1.0)

        self._logger.info("mission_started", module=self.role, mission_id=mission_id)

        await self._publish(
            "discovery.orchestrator.planned",
            payload={"mission_id": mission_id, "research_question": question, "context": context},
            correlation_id=mission_id,
        )

        await self._advance_mission(mission_id)

    async def start_mission(
        self,
        research_question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import secrets
        mission_id = f"mission_{secrets.token_hex(8)}"
        self._active_missions[mission_id] = {
            "question": research_question,
            "mission_id": mission_id,
            "phase": "planning",
            "context": context or {},
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._publish(
            "discovery.mission.start",
            payload={"mission_id": mission_id, "research_question": research_question, "context": context or {}},
            correlation_id=mission_id,
            priority=EventPriority.HIGH,
        )
        return {"mission_id": mission_id, "status": "started"}

    async def _advance_mission(self, mission_id: str) -> None:
        mission = self._active_missions.get(mission_id)
        if not mission:
            return
        await self._publish(
            "discovery.orchestrator.advance",
            payload={
                "mission_id": mission_id,
                "research_question": mission["question"],
                "phase": mission["phase"],
                "context": mission.get("context", {}),
            },
            correlation_id=mission_id,
        )

    async def _on_literature_complete(self, event: SystemEvent) -> None:
        mission_id = event.payload.get("mission_id", "")
        if mission_id in self._active_missions:
            self._active_missions[mission_id]["phase"] = "ideation"
            self._logger.info("phase_ideation", module=self.role, mission_id=mission_id)

    async def _on_hypothesis_complete(self, event: SystemEvent) -> None:
        mission_id = event.payload.get("mission_id", "")
        if mission_id in self._active_missions:
            self._active_missions[mission_id]["phase"] = "evaluation"
            self._logger.info("phase_evaluation", module=self.role, mission_id=mission_id)

    async def _on_critique_complete(self, event: SystemEvent) -> None:
        pass

    async def _on_simulation_complete(self, event: SystemEvent) -> None:
        pass

    async def _on_uncertainty_complete(self, event: SystemEvent) -> None:
        pass

    async def _on_synthesis_complete(self, event: SystemEvent) -> None:
        mission_id = event.payload.get("mission_id", "")
        if mission_id in self._active_missions:
            self._active_missions[mission_id]["phase"] = "complete"
            self._logger.info("mission_complete", module=self.role, mission_id=mission_id)
            await self._publish(
                "discovery.mission.completed",
                payload={
                    "mission_id": mission_id,
                    "research_question": self._active_missions[mission_id]["question"],
                    "status": "completed",
                    "results": event.payload.get("results", {}),
                    "elapsed": (datetime.now(timezone.utc) - datetime.fromisoformat(
                        self._active_missions[mission_id]["started_at"])).total_seconds(),
                },
                correlation_id=mission_id,
                priority=EventPriority.HIGH,
            )
            del self._active_missions[mission_id]

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        question = mission.get("research_question", "")
        if not question:
            return {"status": "error", "error": "No research_question provided"}
        return await self.start_mission(question, mission.get("context"))
