"""Uncertainty Oracle — quantifies uncertainty in every result.

The Uncertainty Oracle operates after the Adversarial Critic has
reviewed the findings. It is responsible for:
  1. Quantifying measurement uncertainty in experimental metrics
  2. Estimating model/formulation uncertainty (parameter sensitivity)
  3. Assessing completeness uncertainty (what haven't we measured?)
  4. Producing calibrated confidence intervals for every reported value
  5. Flagging results that are too uncertain to support strong conclusions

Uncertainty dimensions:
  - Aleatoric: Inherent randomness / irreducible noise
  - Epistemic: Reducible via more data or better experiments
  - Structural: Model / simulation framework limitations
  - Completeness: Gaps in what was measured vs. what matters

Event topics:
  Subscribes to: discovery.uncertainty.assess
  Publishes to:  discovery.uncertainty.results
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.events.bus import SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


@dataclass
class UncertaintyEstimate:
    """Quantified uncertainty for a single metric or claim."""

    metric_name: str
    value: float
    confidence_interval: tuple[float, float]  # 95% CI
    uncertainty_type: str = "aleatoric"  # aleatoric | epistemic | structural
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.5  # Overall confidence score [0, 1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "confidence_interval": list(self.confidence_interval),
            "uncertainty_type": self.uncertainty_type,
            "sources": self.sources,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class UncertaintyReport:
    """Complete uncertainty assessment for a set of experimental results."""

    overall_confidence: float = 0.0  # 0-1
    estimates: list[UncertaintyEstimate] = field(default_factory=list)
    high_uncertainty_flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    uncertainty_decomposition: dict[str, float] = field(default_factory=dict)
    completeness_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_confidence": round(self.overall_confidence, 3),
            "estimates": [e.to_dict() for e in self.estimates],
            "high_uncertainty_flags": self.high_uncertainty_flags,
            "recommendations": self.recommendations,
            "uncertainty_decomposition": self.uncertainty_decomposition,
            "completeness_gaps": self.completeness_gaps,
        }


class UncertaintyOracleAgent(DiscoveryAgent):
    """Quantifies and decomposes uncertainty across all experimental results.

    Provides calibrated confidence assessment to prevent over-interpretation
    of noisy or incomplete findings.
    """

    def __init__(
        self,
        name: str = "Uncertainty Oracle",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Uncertainty Oracle",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.uncertainty.assess", self._on_assessment_request)
        self._logger.info("uncertainty_oracle_ready", module=self.role)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_assessment_request(self, event: SystemEvent) -> None:
        """Handle an uncertainty assessment request."""
        research_question = event.payload.get("research_question", "")
        mission_id = event.payload.get("mission_id", "")
        context = event.payload.get("context", {})

        if not research_question:
            return

        self._logger.info(
            "uncertainty_assessment_started",
            module=self.role,
            mission_id=mission_id,
        )

        self._store_episode(
            episode_type="uncertainty_assessment_started",
            payload={"mission_id": mission_id},
            importance=0.7,
        )

        # Extract prior results from context
        experiment_data = context.get("experiment_results", {})
        critique_data = context.get("critique_results", {})

        # Run the assessment
        report = await self._assess_uncertainty(
            research_question=research_question,
            experiment_data=experiment_data,
            critique_data=critique_data,
        )

        # Store key uncertainties in semantic memory
        for est in report.estimates[:3]:
            self._store_fact(
                concept=f"uncertainty_{mission_id[:8]}",
                relation=f"metric_{est.metric_name}",
                target=f"CI={est.confidence_interval}",
                confidence=est.confidence,
            )

        self._store_episode(
            episode_type="uncertainty_assessment_completed",
            payload={
                "mission_id": mission_id,
                "overall_confidence": report.overall_confidence,
                "high_uncertainty_flags": len(report.high_uncertainty_flags),
            },
            importance=0.8,
        )

        # Publish results
        await self._publish(
            topic="discovery.uncertainty.results",
            payload={
                "mission_id": mission_id,
                "research_question": research_question,
                "status": "completed",
                "results": report.to_dict(),
            },
            correlation_id=mission_id,
        )

        self._logger.info(
            "uncertainty_assessment_completed",
            module=self.role,
            mission_id=mission_id,
            overall_confidence=round(report.overall_confidence, 3),
        )

    # ------------------------------------------------------------------
    # Assessment engine
    # ------------------------------------------------------------------

    async def _assess_uncertainty(
        self,
        research_question: str,
        experiment_data: dict[str, Any] | None = None,
        critique_data: dict[str, Any] | None = None,
    ) -> UncertaintyReport:
        """Execute the full uncertainty assessment pipeline.

        Quantifies uncertainty across four dimensions:
          1. Aleatoric (random noise in measurements)
          2. Epistemic (limited samples / knowledge)
          3. Structural (model limitations)
          4. Completeness (what was not measured)
        """
        exp_data = experiment_data or {}
        crit_data = critique_data or {}
        aggregate = exp_data.get("aggregate", {})
        avg_metrics = aggregate.get("average_metrics", {})
        metric_stddevs = aggregate.get("metric_stddevs", {})
        replicates = exp_data.get("replicates", [])

        estimates: list[UncertaintyEstimate] = []
        high_flags: list[str] = []
        recommendations: list[str] = []
        completeness_gaps: list[str] = []

        # --- 1. Aleatoric uncertainty (from replicate variability) ---
        if isinstance(avg_metrics, dict):
            for metric_name, mean_val in avg_metrics.items():
                std_val = None
                if isinstance(metric_stddevs, dict):
                    std_val = metric_stddevs.get(metric_name)
                else:
                    # Compute from replicates
                    vals = [
                        r.get("metrics", {}).get(metric_name, 0.0)
                        for r in replicates
                        if isinstance(r, dict)
                    ]
                    if len(vals) >= 2:
                        m = sum(vals) / len(vals)
                        std_val = math.sqrt(
                            sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
                        )

                if std_val is not None and isinstance(std_val, (int, float)):
                    # 95% CI = mean ± 1.96 * SEM (standard error of the mean)
                    n_replicates = len(replicates) if replicates else 1
                    sem = std_val / math.sqrt(max(n_replicates, 1))
                    ci_lower = round(mean_val - 1.96 * sem, 4)
                    ci_upper = round(mean_val + 1.96 * sem, 4)

                    # Determine confidence from CI width
                    ci_width = ci_upper - ci_lower
                    normalized_width = min(ci_width / max(abs(mean_val), 0.01), 1.0)
                    confidence = max(0.0, 1.0 - normalized_width)

                    estimate = UncertaintyEstimate(
                        metric_name=metric_name,
                        value=round(mean_val, 4),
                        confidence_interval=(ci_lower, ci_upper),
                        uncertainty_type="aleatoric",
                        sources=[
                            f"Variation across {n_replicates} replicates",
                            f"Standard error of mean = {sem:.4f}",
                        ],
                        confidence=round(confidence, 3),
                    )
                    estimates.append(estimate)

                    if confidence < 0.3:
                        high_flags.append(
                            f"'{metric_name}' has high aleatoric uncertainty "
                            f"(CI width = {ci_width:.3f}) — result is not reliable"
                        )

        # --- 2. Epistemic uncertainty (from limited data) ---
        n_replicates = len(replicates) if replicates else 0
        if n_replicates < 10:
            epistemic_penalty = (10 - n_replicates) / 20.0  # 0 to 0.5
            for est in estimates:
                est.confidence = max(0.0, est.confidence - epistemic_penalty)
                est.uncertainty_type = "epistemic"
                est.sources.append(
                    f"Epistemic penalty: only {n_replicates} of 10 recommended replicates"
                )

            if epistemic_penalty > 0.3:
                high_flags.append(
                    f"Only {n_replicates} replicates available — epistemic uncertainty "
                    "is high. Results may change substantially with more data."
                )

        # --- 3. Structural uncertainty (from critique) ---
        crit_issues = (
            crit_data.get("issues", [])
            if isinstance(crit_data, dict)
            else []
        )
        if crit_issues:
            # Apply structural penalty based on severity
            major_issues = sum(
                1 for i in crit_issues
                if isinstance(i, dict) and i.get("severity") == "MAJOR"
            )
            critical_issues = sum(
                1 for i in crit_issues
                if isinstance(i, dict) and i.get("severity") == "CRITICAL"
            )
            structural_penalty = (major_issues * 0.05 + critical_issues * 0.15)
            for est in estimates:
                est.confidence = max(0.0, est.confidence - structural_penalty)
                est.sources.append(
                    f"Structural penalty from critique: {major_issues} major, "
                    f"{critical_issues} critical issues"
                )

            if structural_penalty > 0.3:
                high_flags.append(
                    "Structural uncertainty is high due to critique issues — "
                    "experimental design or analysis may be fundamentally flawed"
                )

        # --- 4. Completeness gaps ---
        if isinstance(avg_metrics, dict):
            completeness_gaps.extend(self._identify_completeness_gaps(
                research_question,
                list(avg_metrics.keys()),
            ))

        # --- Recommendations ---
        recommendations.extend(self._generate_recommendations(
            estimates, high_flags, completeness_gaps
        ))

        # --- Overall confidence ---
        overall_confidence = 0.0
        if estimates:
            overall_confidence = sum(e.confidence for e in estimates) / len(estimates)

        # Decompose uncertainty by type
        decomposition: dict[str, float] = {}
        for ut in ["aleatoric", "epistemic", "structural"]:
            related = [e for e in estimates if e.uncertainty_type == ut]
            if related:
                decomposition[ut] = round(
                    sum(1 - e.confidence for e in related) / len(related), 3
                )

        return UncertaintyReport(
            overall_confidence=round(overall_confidence, 3),
            estimates=estimates,
            high_uncertainty_flags=high_flags,
            recommendations=recommendations,
            uncertainty_decomposition=decomposition,
            completeness_gaps=completeness_gaps,
        )

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------

    def _identify_completeness_gaps(
        self,
        research_question: str,
        measured_metrics: list[str],
    ) -> list[str]:
        """Identify what important aspects were not measured."""
        gaps: list[str] = []

        all_standard = {
            "specialization_index": "Behavioural specialisation",
            "communication_entropy": "Communication diversity",
            "tool_adoption_rate": "Tool/cultural diffusion",
            "memory_persistence_rate": "Memory retention",
            "lineage_survival_rate": "Lineage extinction risk",
            "trade_network_density": "Economic network structure",
            "reputation_convergence": "Social consensus dynamics",
        }

        measured_set = set(measured_metrics)
        for metric_name, description in all_standard.items():
            if metric_name not in measured_set:
                gaps.append(
                    f"'{metric_name}' ({description}) was not measured — "
                    f"this aspect of '{research_question[:40]}' may hide important effects"
                )

        return gaps[:5]

    def _generate_recommendations(
        self,
        estimates: list[UncertaintyEstimate],
        high_flags: list[str],
        completeness_gaps: list[str],
    ) -> list[str]:
        """Generate actionable recommendations to reduce uncertainty."""
        recs: list[str] = []

        if high_flags:
            recs.append(
                "Increase replicate count to 20+ to reduce aleatoric uncertainty "
                "to acceptable levels"
            )
        if completeness_gaps:
            recs.append(
                "Add missing standard metrics to the experimental measurement pipeline"
            )
        if estimates:
            low_conf = [e for e in estimates if e.confidence < 0.5]
            if low_conf:
                recs.append(
                    f"Focus experimental improvements on the {len(low_conf)} metric(s) "
                    f"with lowest confidence: {', '.join(e.metric_name for e in low_conf[:3])}"
                )

        recs.append(
            "Perform sensitivity analysis across a broad parameter range to bound "
            "structural uncertainty"
        )

        return recs[:5]

    # ------------------------------------------------------------------
    # DiscoveryAgent abstract implementation
    # ------------------------------------------------------------------

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        """Handle an uncertainty assessment mission directly."""
        research_question = mission.get("research_question", "")
        if not research_question:
            return {"status": "error", "error": "No research_question provided"}

        context = mission.get("context", {})
        report = await self._assess_uncertainty(
            research_question=research_question,
            experiment_data=context.get("experiment_results"),
            critique_data=context.get("critique_results"),
        )

        return {
            "status": "completed",
            "results": report.to_dict(),
        }
