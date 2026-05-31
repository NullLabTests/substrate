from __future__ import annotations

import secrets
from typing import Any

from core.events.bus import SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


class HypothesisForgeAgent(DiscoveryAgent):
    def __init__(
        self,
        name: str = "Hypothesis Forge",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Hypothesis Forge",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.literature.complete", self._on_literature_complete)
        self._subscribe("discovery.hypothesis.generate", self._on_generate_request)
        self._logger.info("hypothesis_forge_ready", module=self.role)

    async def _on_literature_complete(self, event: SystemEvent) -> None:
        question = event.payload.get("research_question", "")
        mission_id = event.payload.get("mission_id", "")
        lit_results = event.payload.get("results", {})

        self._logger.info("hypothesis_generation_started", module=self.role, mission_id=mission_id)
        self._store_episode("generation_started", {"mission_id": mission_id}, importance=0.8)

        bank = await self._generate_hypotheses(question, lit_results)

        for h in bank.get("candidates", []):
            hid = h.get("id", "?")
            self._store_fact("hypothesis", f"{hid}_{mission_id[:8]}", h.get("hypothesis", "")[:128], confidence=h.get("composite_score", 0.5))

        self._store_episode("generation_completed", {"mission_id": mission_id, "candidates": len(bank.get("candidates", []))}, importance=0.9)

        await self._publish(
            "discovery.hypothesis.complete",
            payload={
                "mission_id": mission_id,
                "research_question": question,
                "status": "completed",
                "results": bank,
            },
            correlation_id=mission_id,
        )
        self._logger.info("hypothesis_generation_completed", module=self.role, mission_id=mission_id)

    async def _on_generate_request(self, event: SystemEvent) -> None:
        await self._on_literature_complete(event)

    async def _generate_hypotheses(
        self, question: str, literature: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        lit = literature or {}
        facts = lit.get("established_facts", [])
        questions = lit.get("open_questions", [])

        candidates = self._placeholder_hypotheses(question, facts, questions)
        ranked = [h["id"] for h in sorted(candidates, key=lambda x: x.get("composite_score", 0), reverse=True)]
        return {"candidates": candidates, "ranked_order": ranked, "coverage_gaps": []}

    def _placeholder_hypotheses(
        self, question: str,
        facts: list[dict[str, Any]], questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import math
        candidates = []
        for i in range(min(3, max(1, len(facts)))):
            candidates.append({
                "id": f"H-{i + 1}",
                "hypothesis": f"Systematic investigation of '{question[:60]}' reveals that emergent properties scale non-linearly with interaction complexity",
                "mechanism": "Multi-agent interactions produce higher-order effects not predictable from individual agent behavior alone",
                "predictions": [
                    f"Increasing agent count amplifies emergent complexity up to a critical threshold",
                    f"Communication topology mediates the rate of collective discovery",
                ],
                "novelty_score": round(0.5 + 0.4 * math.sin(i + 1), 2),
                "feasibility_score": round(0.6 + 0.3 * math.cos(i), 2),
                "impact_if_true": round(0.7 + 0.25 * (1 if i == 0 else 0), 2),
                "composite_score": 0.0,
                "builds_upon": [f.get("fact", "")[:40] for f in facts[:2]],
                "key_uncertainties": ["Parameter sensitivity", "Boundary conditions"],
            })
        for h in candidates:
            n = h.get("novelty_score", 0)
            f = h.get("feasibility_score", 0)
            im = h.get("impact_if_true", 0)
            h["composite_score"] = round(n * 0.3 + f * 0.3 + im * 0.4, 2)
        return candidates

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        question = mission.get("research_question", "")
        if not question:
            return {"status": "error", "error": "No research_question provided"}
        literature = mission.get("context", {}).get("literature_results")
        bank = await self._generate_hypotheses(question, literature)
        return {"status": "completed", "results": bank}
