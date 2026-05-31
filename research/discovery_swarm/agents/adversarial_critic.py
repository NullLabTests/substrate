from __future__ import annotations

from typing import Any

from core.events.bus import SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


class AdversarialCriticAgent(DiscoveryAgent):
    def __init__(
        self,
        name: str = "Adversarial Critic",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Adversarial Critic",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.hypothesis.complete", self._on_hypotheses_ready)
        self._subscribe("discovery.critique.review", self._on_review_request)
        self._logger.info("adversarial_critic_ready", module=self.role)

    async def _on_hypotheses_ready(self, event: SystemEvent) -> None:
        mission_id = event.payload.get("mission_id", "")
        question = event.payload.get("research_question", "")
        hyp_results = event.payload.get("results", {})

        self._logger.info("critique_started", module=self.role, mission_id=mission_id)
        self._store_episode("critique_started", {"mission_id": mission_id}, importance=0.8)

        critique = await self._critique_hypotheses(hyp_results)

        surviving = critique.get("surviving_hypotheses", [])
        rejected = critique.get("rejected_hypotheses", [])
        self._store_fact("critique", f"verdict_{mission_id[:8]}", f"{len(surviving)} survived, {len(rejected)} rejected", confidence=0.85)
        self._store_episode("critique_completed", {"mission_id": mission_id, "surviving": len(surviving)}, importance=0.9)

        await self._publish(
            "discovery.critique.complete",
            payload={
                "mission_id": mission_id,
                "research_question": question,
                "status": "completed",
                "results": critique,
            },
            correlation_id=mission_id,
        )
        self._logger.info("critique_completed", module=self.role, mission_id=mission_id)

    async def _on_review_request(self, event: SystemEvent) -> None:
        await self._on_hypotheses_ready(event)

    async def _critique_hypotheses(self, hypothesis_data: dict[str, Any]) -> dict[str, Any]:
        candidates = hypothesis_data.get("candidates", hypothesis_data.get("hypothesis_bank", {}).get("candidates", []))
        critiques = []
        surviving = []
        rejected = []

        for h in candidates:
            h_id = h.get("id", "?")
            score = h.get("composite_score", h.get("novelty_score", 0))
            if score > 0.5:
                critiques.append(self._critique_hypothesis(h))
                surviving.append(h_id)
            else:
                rejected.append({"id": h_id, "reason": "Composite score below threshold", "could_be_revised": True})

        if not candidates:
            return {"critique_matrix": [], "surviving_hypotheses": [], "rejected_hypotheses": []}

        return {
            "critique_matrix": critiques,
            "surviving_hypotheses": surviving,
            "rejected_hypotheses": rejected,
        }

    def _critique_hypothesis(self, hypothesis: dict[str, Any]) -> dict[str, Any]:
        h_id = hypothesis.get("id", "?")
        n = hypothesis.get("novelty_score", 0.5)
        f = hypothesis.get("feasibility_score", 0.5)
        return {
            "hypothesis_id": h_id,
            "logical_consistency": {"score": round(n * 0.8 + 0.2, 2), "issues": []},
            "evidential_support": {"score": round(f * 0.7 + 0.3, 2), "evidence_for": [], "evidence_against": []},
            "alternative_explanations": ["Potential confound from unmeasured variables"],
            "experimental_viability": {"score": round(f, 2), "concerns": []},
            "overall_verdict": "WEAKLY_SUPPORTED" if n > 0.6 else "INCONCLUSIVE",
            "recommended_action": "PROCEED" if n > 0.5 else "MODIFY",
            "detailed_critique": f"H-{h_id} is {'promising' if n > 0.6 else 'preliminary'} but requires more evidence.",
        }

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        hyp_data = mission.get("context", {}).get("hypothesis_results", {})
        critique = await self._critique_hypotheses(hyp_data)
        return {"status": "completed", "results": critique}
