from __future__ import annotations

from typing import Any

from core.events.bus import SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


class LiteratureScoutAgent(DiscoveryAgent):
    def __init__(
        self,
        name: str = "Literature Scout & Synthesizer",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Literature Scout & Synthesizer",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.orchestrator.planned", self._on_mission_planned)
        self._subscribe("discovery.literature.survey", self._on_survey_request)
        self._logger.info("literature_scout_ready", module=self.role)

    async def _on_mission_planned(self, event: SystemEvent) -> None:
        question = event.payload.get("research_question", "")
        mission_id = event.payload.get("mission_id", "")
        context = event.payload.get("context", {})
        if not question:
            return
        self._logger.info("literature_survey_started", module=self.role, mission_id=mission_id)
        self._store_episode("survey_started", {"mission_id": mission_id, "question": question[:80]}, importance=0.7)

        survey = await self._survey_literature(question, context)

        self._store_fact("literature", f"survey_{mission_id[:8]}", question[:128], confidence=0.8)
        self._store_episode("survey_completed", {"mission_id": mission_id, "facts": len(survey.get("established_facts", []))}, importance=0.8)

        await self._publish(
            "discovery.literature.complete",
            payload={
                "mission_id": mission_id,
                "research_question": question,
                "status": "completed",
                "results": survey,
            },
            correlation_id=mission_id,
        )
        self._logger.info("literature_survey_completed", module=self.role, mission_id=mission_id)

    async def _on_survey_request(self, event: SystemEvent) -> None:
        await self._on_mission_planned(event)

    async def _survey_literature(
        self, question: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sub_problems = context.get("sub_problems", []) if context else []
        facts, open_qs, constraints = self._placeholder_survey(question, sub_problems)
        return {
            "established_facts": facts,
            "open_questions": open_qs,
            "key_constraints": constraints,
            "promising_directions": [
                f"Computational approaches to {question[:60]}",
                "Multi-scale modeling frameworks",
            ],
            "dead_ends": ["Purely theoretical approaches without empirical grounding"],
        }

    def _placeholder_survey(
        self, question: str, sub_problems: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        facts: list[dict[str, Any]] = [
            {"fact": f"Significant prior work exists on aspects of '{question[:60]}'", "confidence": 0.9, "source": "cross-disciplinary literature"},
            {"fact": "Computational simulation is a well-established methodology for complex systems", "confidence": 0.95, "source": "methodological consensus"},
        ]
        for sp in sub_problems[:3]:
            sp_id = sp.get("id", "?")
            facts.append({
                "fact": f"Sub-problem {sp_id} has partial precedent in adjacent domains",
                "confidence": 0.6,
                "source": f"domain mapping for {sp.get('sub_problem', '')[:40]}",
            })
        questions: list[dict[str, Any]] = [
            {"question": f"What are the fundamental mechanisms underlying '{question[:60]}'?", "importance": "HIGH"},
            {"question": "Which simulation parameters best capture the phenomena of interest?", "importance": "HIGH"},
            {"question": "What is the appropriate spatiotemporal scale for modeling?", "importance": "MEDIUM"},
        ]
        constraints: list[dict[str, Any]] = [
            {"constraint": "Simulation fidelity vs. computational cost tradeoff", "severity": "SOFT"},
            {"constraint": "Available empirical data for validation", "severity": "HARD"},
        ]
        return facts, questions, constraints

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        question = mission.get("research_question", "")
        if not question:
            return {"status": "error", "error": "No research_question provided"}
        context = mission.get("context", {})
        survey = await self._survey_literature(question, context)
        return {"status": "completed", "results": survey}
