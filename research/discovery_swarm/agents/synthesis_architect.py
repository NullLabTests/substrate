"""Synthesis & Proposal Architect — composes publication-ready research proposals.

The Synthesis Architect is the final agent in the discovery pipeline. It
is activated after all prior phases (literature, hypothesis, experiment,
critique, uncertainty) have completed. Its responsibilities:
  1. Aggregate results from all prior phases into a coherent narrative
  2. Compose a structured research proposal following scientific format
  3. Highlight key findings with appropriate confidence caveats
  4. Identify limitations and future work directions
  5. Format output as a publication-ready Markdown document
  6. Package replication information (git hash, seeds, dependencies)

Report structure:
  - Abstract (250 words)
  - Introduction (context, gap, hypothesis)
  - Methods (experiment design, configuration, statistical approach)
  - Results (metrics, statistical tests, uncertainty bounds)
  - Discussion (interpretation, limitations, alternatives)
  - Conclusion (summary, implications, open questions)
  - Replication package (configuration, seeds, dependencies)

Event topics:
  Subscribes to: discovery.synthesis.compose
  Publishes to:  discovery.synthesis.complete
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.events.bus import EventPriority, SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


@dataclass
class ResearchProposal:
    """Complete publication-ready research proposal."""

    title: str
    abstract: str
    introduction: str
    methods: str
    results: str
    discussion: str
    conclusion: str
    replication_package: dict[str, Any] = field(default_factory=dict)
    figures: list[dict[str, Any]] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_markdown(self) -> str:
        """Render the proposal as a formatted Markdown document."""
        lines: list[str] = [
            f"# {self.title}",
            "",
            f"*Generated: {self.created_at}*",
            "",
            "---",
            "",
            "## Abstract",
            "",
            self.abstract,
            "",
            "---",
            "",
            "## 1. Introduction",
            "",
            self.introduction,
            "",
            "---",
            "",
            "## 2. Methods",
            "",
            self.methods,
            "",
            "---",
            "",
            "## 3. Results",
            "",
            self.results,
            "",
            "---",
            "",
            "## 4. Discussion",
            "",
            self.discussion,
            "",
            "---",
            "",
            "## 5. Conclusion",
            "",
            self.conclusion,
            "",
            "---",
            "",
            "## 6. Replication Package",
            "",
        ]

        for key, value in self.replication_package.items():
            lines.append(f"- **{key}**: `{value}`")

        if self.references:
            lines.extend(["", "---", "", "## References", ""])
            for i, ref in enumerate(self.references, 1):
                lines.append(f"[{i}] {ref}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "abstract": self.abstract,
            "introduction": self.introduction,
            "methods": self.methods,
            "results": self.results,
            "discussion": self.discussion,
            "conclusion": self.conclusion,
            "replication_package": self.replication_package,
            "figures": self.figures,
            "references": self.references,
            "markdown": self.to_markdown(),
        }


class SynthesisProposalArchitectAgent(DiscoveryAgent):
    """Composes structured, publication-ready research proposals from
    the outputs of all prior discovery phases.

    Synthesises literature context, hypotheses tested, experimental
    design, results, critique outcomes, and uncertainty quantification
    into a coherent scientific narrative.
    """

    def __init__(
        self,
        name: str = "Synthesis & Proposal Architect",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Synthesis & Proposal Architect",
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
        self._subscribe("discovery.synthesis.compose", self._on_compose_request)
        self._logger.info("synthesis_architect_ready", module=self.role)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_compose_request(self, event: SystemEvent) -> None:
        """Handle a proposal composition request from the orchestrator."""
        research_question = event.payload.get("research_question", "")
        mission_id = event.payload.get("mission_id", "")
        context = event.payload.get("context", {})

        if not research_question:
            return

        self._logger.info(
            "synthesis_started",
            module=self.role,
            mission_id=mission_id,
        )

        self._store_episode(
            episode_type="synthesis_started",
            payload={"mission_id": mission_id},
            importance=0.9,
        )

        # Extract all prior phase results from context
        literature_results = context.get("literature_results", {})
        hypothesis_results = context.get("hypothesis_results", {})
        experiment_results = context.get("experiment_results", {})
        critique_results = context.get("critique_results", {})
        uncertainty_results = context.get("uncertainty_results", {})

        # Compose the proposal
        proposal = await self._compose_proposal(
            research_question=research_question,
            literature=literature_results,
            hypothesis=hypothesis_results,
            experiment=experiment_results,
            critique=critique_results,
            uncertainty=uncertainty_results,
        )

        # Store in semantic memory
        self._store_fact(
            concept=f"proposal_{mission_id[:8]}",
            relation="title",
            target=proposal.title[:128],
            confidence=0.95,
        )

        self._store_episode(
            episode_type="synthesis_completed",
            payload={
                "mission_id": mission_id,
                "title": proposal.title,
                "word_count": len(proposal.to_markdown().split()),
            },
            importance=1.0,
        )

        # Publish the completed proposal
        await self._publish(
            topic="discovery.synthesis.complete",
            payload={
                "mission_id": mission_id,
                "research_question": research_question,
                "status": "completed",
                "results": proposal.to_dict(),
            },
            correlation_id=mission_id,
            priority=EventPriority.HIGH,
        )

        self._logger.info(
            "synthesis_completed",
            module=self.role,
            mission_id=mission_id,
            title=proposal.title[:60],
        )

    # ------------------------------------------------------------------
    # Composition engine
    # ------------------------------------------------------------------

    async def _compose_proposal(
        self,
        research_question: str,
        literature: dict[str, Any] | None = None,
        hypothesis: dict[str, Any] | None = None,
        experiment: dict[str, Any] | None = None,
        critique: dict[str, Any] | None = None,
        uncertainty: dict[str, Any] | None = None,
    ) -> ResearchProposal:
        """Synthesise all prior results into a structured research proposal.

        In production, each section would be drafted by an LLM call with
        the Synthesis & Proposal Architect prompt. The placeholder
        implementation demonstrates the structured output format.
        """
        lit = literature or {}
        hyp = hypothesis or {}
        exp = experiment or {}
        crit = critique or {}
        unc = uncertainty or {}

        # --- Extract key data from prior phases ---
        lit_synthesis = lit.get("results", lit)
        hyp_results = hyp.get("results", hyp)
        exp_results = exp.get("results", exp)
        crit_results = crit.get("results", crit)
        unc_results = unc.get("results", unc)

        # Hypothesis
        top_hyp = ""
        hypotheses_list = []
        if isinstance(hyp_results, dict):
            hypotheses_list = hyp_results.get("hypotheses", []) if isinstance(hyp_results.get("hypotheses"), list) else []
            top_hyp_dict = hyp_results.get("top_hypothesis", {})
            if isinstance(top_hyp_dict, dict):
                top_hyp = top_hyp_dict.get("statement", "")

        # Experiment results
        avg_metrics = {}
        if isinstance(exp_results, dict):
            agg = exp_results.get("aggregate", {})
            if isinstance(agg, dict):
                avg_metrics = agg.get("average_metrics", {})

        # Critique
        critique_assessment = ""
        if isinstance(crit_results, dict):
            critique_assessment = crit_results.get("overall_assessment", "")

        # Uncertainty
        overall_confidence = 0.0
        if isinstance(unc_results, dict):
            overall_confidence = unc_results.get("overall_confidence", 0.0)

        # --- Build the replication package ---
        replication = await self._build_replication_package()

        # --- Compose each section ---
        title = f"Discovery Report: {research_question[:80]}"

        abstract = (
            f"This report investigates the research question: '{research_question}'. "
            f"Through a systematic multi-agent discovery pipeline, we formulated and "
            f"tested {max(len(hypotheses_list), 1)} candidate hypotheses using controlled "
            f"simulation experiments on the Substrate platform. "
        )

        if isinstance(avg_metrics, dict) and avg_metrics:
            metrics_desc = "; ".join(
                f"{k}: {v:.3f}" for k, v in list(avg_metrics.items())[:4]
            )
            abstract += (
                f"Key metrics observed include {metrics_desc}. "
            )

        abstract += (
            f"The findings were subjected to rigorous adversarial critique ({critique_assessment.lower() if critique_assessment else 'reviewed'}) "
            f"and uncertainty quantification (overall confidence: {overall_confidence:.2f}). "
            f"We identify key open questions and propose specific next steps for advancing "
            f"understanding of this topic."
        )

        # Introduction
        knowledge_gaps_list = []
        if isinstance(lit_synthesis, dict):
            knowledge_gaps_list = lit_synthesis.get("knowledge_gaps", []) if isinstance(lit_synthesis.get("knowledge_gaps"), list) else []
        gaps_bullets = "\n".join(
            f"- {g}" for g in knowledge_gaps_list[:3]
        ) if knowledge_gaps_list else "- Limited prior work directly addressing this question in a simulation framework"

        introduction = (
            f"The question of '{research_question}' represents an important frontier in "
            f"our understanding of complex adaptive systems. "
            f"While prior work has explored related phenomena, significant knowledge gaps remain:\n\n"
            f"{gaps_bullets}\n\n"
            f"To address these gaps, we formulated the following hypothesis:\n\n"
            f"> {top_hyp or research_question}\n\n"
            f"In this work, we present a systematic simulation-based investigation using "
            f"the Substrate platform — a tick-based asynchronous runtime for persistent "
            f"multi-agent systems."
        )

        # Methods
        methods = (
            f"## Experimental Design\n\n"
            f"We employed a controlled simulation experiment on the Substrate platform. "
            f"The simulation was configured with standard parameters including population size, "
            f"interaction rules, and environmental constraints.\n\n"
            f"## Key Parameters\n\n"
        )

        if isinstance(exp_results, dict):
            config = exp_results.get("config", {})
            if isinstance(config, dict):
                config_overrides = config.get("config_overrides", {})
                if isinstance(config_overrides, dict):
                    for param, value in config_overrides.items():
                        methods += f"- **{param}**: `{value}`\n"

        methods += (
            f"\n## Statistical Approach\n\n"
            f"Each experiment was run with {exp_results.get('aggregate', {}).get('replicate_count', 'N')} replicates. "
            f"Metrics were computed following the standardised Substrate research framework. "
            f"Direction consistency was assessed across replicates. "
            f"Uncertainty was quantified using 95% confidence intervals derived from "
            f"replicate variability.\n\n"
        )

        if isinstance(exp_results, dict):
            interventions = []
            if isinstance(config, dict):
                interventions = config.get("interventions", [])
            if interventions:
                methods += "## Interventions\n\n"
                for inv in interventions:
                    if isinstance(inv, dict):
                        methods += (
                            f"- Tick {inv.get('tick', '?')}: {inv.get('type', 'unknown')} "
                            f"with params {inv.get('params', {})}\n"
                        )

        # Results
        results_str = "## Primary Metrics\n\n"
        if isinstance(avg_metrics, dict) and avg_metrics:
            results_str += "| Metric | Value |\n|--------|-------|\n"
            for metric_name, value in avg_metrics.items():
                results_str += f"| {metric_name} | {value:.4f} |\n"
        else:
            results_str += "Metrics were computed across all replicates. See replication package for full data.\n"

        results_str += "\n## Critique Summary\n\n"
        if critique_assessment:
            results_str += f"**Overall assessment**: {critique_assessment}\n\n"

        if isinstance(crit_results, dict):
            issues = crit_results.get("issues", [])
            if isinstance(issues, list) and issues:
                results_str += "### Key Issues Identified\n\n"
                for issue in issues[:5]:
                    if isinstance(issue, dict):
                        results_str += (
                            f"- **[{issue.get('severity', 'INFO')}]** "
                            f"{issue.get('description', '')}\n"
                        )

        results_str += "\n## Uncertainty Quantification\n\n"
        results_str += f"**Overall confidence**: {overall_confidence:.2f}\n\n"
        if isinstance(unc_results, dict):
            flags = unc_results.get("high_uncertainty_flags", [])
            if isinstance(flags, list) and flags:
                results_str += "### High Uncertainty Flags\n\n"
                for flag in flags[:3]:
                    results_str += f"- {flag}\n"

        # Discussion
        discussion = (
            f"The findings from this investigation provide insights into '{research_question}'. "
            f"While the results are broadly consistent with the proposed hypothesis, "
            f"several important caveats must be considered.\n\n"
        )

        if isinstance(crit_results, dict):
            alternatives = crit_results.get("alternative_hypotheses", [])
            if isinstance(alternatives, list) and alternatives:
                discussion += "### Alternative Explanations\n\n"
                for alt in alternatives[:3]:
                    discussion += f"- {alt}\n"
                discussion += "\n"

        if isinstance(crit_results, dict):
            boundaries = crit_results.get("boundary_conditions", [])
            if isinstance(boundaries, list) and boundaries:
                discussion += "### Boundary Conditions\n\n"
                for bc in boundaries[:3]:
                    discussion += f"- {bc}\n"
                discussion += "\n"

        if isinstance(unc_results, dict):
            gaps = unc_results.get("completeness_gaps", [])
            if isinstance(gaps, list) and gaps:
                discussion += "### Completeness Gaps\n\n"
                for gap in gaps[:3]:
                    discussion += f"- {gap}\n"
                discussion += "\n"

        # Conclusion
        conclusion = (
            f"In summary, this investigation of '{research_question}' has yielded "
            f"preliminary findings that warrant further investigation. "
        )

        if overall_confidence > 0.7:
            conclusion += (
                "The results are robust with high confidence, suggesting that "
                "the proposed mechanisms are likely operating as hypothesised."
            )
        elif overall_confidence > 0.4:
            conclusion += (
                "The results are moderately confident and consistent with the hypothesis, "
                "but require additional replication and robustness testing."
            )
        else:
            conclusion += (
                "The results carry significant uncertainty and should be interpreted "
                "with caution. Further experimental refinement is needed."
            )

        conclusion += (
            "\n\n### Open Questions\n\n"
            "- Do the observed effects generalise to different parameter regimes?\n"
            "- Are the findings robust to alternative modelling assumptions?\n"
            "- What are the underlying mechanisms driving the observed patterns?\n"
            "- Would different swarm configurations reach similar conclusions?\n"
        )

        # References
        references: list[str] = [
            "Substrate Platform Documentation (2024). Tick-based simulation runtime for persistent multi-agent systems.",
        ]

        return ResearchProposal(
            title=title,
            abstract=abstract,
            introduction=introduction,
            methods=methods,
            results=results_str,
            discussion=discussion,
            conclusion=conclusion,
            replication_package=replication,
            figures=[],
            references=references,
        )

    # ------------------------------------------------------------------
    # Replication package
    # ------------------------------------------------------------------

    async def _build_replication_package(self) -> dict[str, Any]:
        """Collect replication metadata from the environment.

        Captures:
          - Current git hash
          - Python version
          - Dependencies
          - Platform information
        """
        package: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Git hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                package["git_hash"] = result.stdout.strip()
        except Exception:
            package["git_hash"] = "unknown"

        # Try to get git describe as well
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                package["git_tag"] = result.stdout.strip()
        except Exception:
            pass

        # Python version
        import sys
        package["python_version"] = sys.version

        # Platform
        import platform
        package["platform"] = platform.platform()

        # Dependencies (read from pyproject.toml if available)
        try:
            import tomllib
            from pathlib import Path
            pyproject = Path("pyproject.toml")
            if pyproject.exists():
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                deps = data.get("project", {}).get("dependencies", [])
                package["dependencies"] = deps
        except Exception:
            package["dependencies"] = []

        return package

    # ------------------------------------------------------------------
    # DiscoveryAgent abstract implementation
    # ------------------------------------------------------------------

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        """Handle a synthesis mission directly."""
        research_question = mission.get("research_question", "")
        if not research_question:
            return {"status": "error", "error": "No research_question provided"}

        context = mission.get("context", {})
        proposal = await self._compose_proposal(
            research_question=research_question,
            literature=context.get("literature_results"),
            hypothesis=context.get("hypothesis_results"),
            experiment=context.get("experiment_results"),
            critique=context.get("critique_results"),
            uncertainty=context.get("uncertainty_results"),
        )

        return {
            "status": "completed",
            "results": proposal.to_dict(),
        }
