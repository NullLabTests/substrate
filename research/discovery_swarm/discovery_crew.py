"""Discovery Crew — creates and launches the full 7-agent swarm as a persistent group.

The DiscoveryCrew orchestrates the lifecycle of all 7 Discovery Swarm agents.
It:
  1. Creates each agent with its role-specific configuration
  2. Initializes all agents in dependency order
  3. Registers each agent with the Substrate Agent Registry
  4. Wires agents to the shared EventBus for async communication
  5. Provides ``start_mission()`` to begin a new discovery investigation
  6. Handles graceful shutdown and state persistence for the entire crew

Usage::

    from research.discovery_swarm import DiscoveryCrew

    crew = DiscoveryCrew()
    await crew.initialize()

    report = await crew.start_mission(
        research_question="What is the nature of dark matter?",
    )

    print(report["results"]["markdown"][:500])

    await crew.shutdown()
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from core.events.bus import EventBus
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry

from research.discovery_swarm.agents.swarm_orchestrator import SwarmOrchestratorAgent
from research.discovery_swarm.agents.literature_scout import LiteratureScoutAgent
from research.discovery_swarm.agents.hypothesis_forge import HypothesisForgeAgent
from research.discovery_swarm.agents.simulation_engineer import SimulationEngineerAgent
from research.discovery_swarm.agents.adversarial_critic import AdversarialCriticAgent
from research.discovery_swarm.agents.uncertainty_oracle import UncertaintyOracleAgent
from research.discovery_swarm.agents.synthesis_architect import SynthesisProposalArchitectAgent


class DiscoveryCrew:
    """Creates, initialises, and manages the full 7-agent discovery swarm.

    The crew runs as a persistent group on the Substrate runtime. Agents
    communicate asynchronously via the shared EventBus. Missions progress
    through the pipeline: literature → hypothesis → experiment → critique
    → uncertainty → synthesis.

    Args:
        event_bus: Shared EventBus instance (created if None).
        registry: Shared AgentRegistry instance (created if None).
        logger: Shared StructuredLogger instance (created if None).
        auto_init: If True, call initialize() at construction time.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        registry: AgentRegistry | None = None,
        logger: StructuredLogger | None = None,
        auto_init: bool = False,
    ) -> None:
        # Shared infrastructure
        self._event_bus: EventBus = event_bus or EventBus()
        self._registry: AgentRegistry = registry or AgentRegistry()
        self._logger: StructuredLogger = logger or StructuredLogger(
            name="discovery_crew",
            level="info",
        )

        self._initialized: bool = False

        # Create all 7 agents (order matters for dependency)
        self.orchestrator = SwarmOrchestratorAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.literature_scout = LiteratureScoutAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.hypothesis_forge = HypothesisForgeAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.simulation_engineer = SimulationEngineerAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.adversarial_critic = AdversarialCriticAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.uncertainty_oracle = UncertaintyOracleAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )
        self.synthesis_architect = SynthesisProposalArchitectAgent(
            event_bus=self._event_bus,
            registry=self._registry,
            logger=self._logger,
        )

        # Ordered list of all agents
        self._agents = [
            self.orchestrator,
            self.literature_scout,
            self.hypothesis_forge,
            self.simulation_engineer,
            self.adversarial_critic,
            self.uncertainty_oracle,
            self.synthesis_architect,
        ]

        if auto_init:
            # Running from non-async context — caller must await
            pass

    # ------------------------------------------------------------------
    # Crew lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialise the EventBus, Registry, and all 7 agents.

        Agents are initialised in order so the orchestrator is ready
        to receive results before downstream agents start.
        """
        self._logger.info("discovery_crew_initializing")
        await self._logger.initialize()

        # Initialise shared infrastructure first
        await self._event_bus.initialize()
        await self._registry.initialize()

        # Initialise all agents (in dependency order)
        for agent in self._agents:
            await agent.initialize()

        # Subscribe the orchestrator to listen for mission result events
        # (handled internally by each agent's subscriptions)

        self._initialized = True
        self._logger.info(
            "discovery_crew_initialized",
            agent_count=len(self._agents),
            agent_names=[a.name for a in self._agents],
        )

    async def shutdown(self) -> None:
        """Gracefully shut down all agents and shared infrastructure.

        Agents are shut down in reverse order (synthesis architect first,
        orchestrator last) so that no agent is waiting for results from
        an already-shutdown agent.
        """
        self._logger.info("discovery_crew_shutting_down")

        # Shut down agents in reverse order
        for agent in reversed(self._agents):
            await agent.shutdown()

        # Shut down shared infrastructure
        await self._registry.shutdown()
        await self._event_bus.shutdown()
        await self._logger.shutdown()

        self._initialized = False
        self._logger.info("discovery_crew_shutdown_complete")

    async def save_state(self) -> dict[str, Any]:
        """Save the state of the entire crew.

        Collects state from each agent and the shared infrastructure.

        Returns:
            A dict with all crew state for persistence/recovery.
        """
        crew_state: dict[str, Any] = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "agents": {},
        }

        for agent in self._agents:
            agent_state = await agent.save_state()
            crew_state["agents"][agent.agent_id] = agent_state

        return crew_state

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore crew state from a previously saved snapshot.

        Args:
            state: The dict from ``save_state()``, or None.
        """
        if not state:
            return

        saved_agents = state.get("agents", {})
        for agent in self._agents:
            if agent.agent_id in saved_agents:
                await agent.load_state(saved_agents[agent.agent_id])

        self._logger.info(
            "discovery_crew_state_loaded",
            agent_count=len(saved_agents),
        )

    # ------------------------------------------------------------------
    # Mission operations
    # ------------------------------------------------------------------

    async def start_mission(
        self,
        research_question: str,
        context: dict[str, Any] | None = None,
        wait_for_completion: bool = True,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Start a new Discovery Mission with the given research question.

        This is the main entry point for scientific discovery. It:
          1. Delegates to the SwarmOrchestrator to start the mission
          2. Optionally awaits completion (collecting results from the bus)
          3. Returns the final DiscoveryReport

        Args:
            research_question: The hard science question to investigate.
            context: Optional additional context (constraints, prior results).
            wait_for_completion: If True, blocks until the mission finishes.
            timeout: Maximum seconds to wait for completion (default 5 min).

        Returns:
            A dict with mission results, including the final report.
        """
        if not self._initialized:
            await self.initialize()

        self._logger.info(
            "crew_mission_starting",
            research_question=research_question[:80],
            wait_for_completion=wait_for_completion,
        )

        # Create a future that will be resolved when the mission completes
        completion_future: asyncio.Future[dict[str, Any]] = asyncio.Future()

        if wait_for_completion:
            # Subscribe to the mission completion event
            sub = self._event_bus.subscribe(
                topic_pattern="discovery.mission.completed",
                handler=lambda e: self._on_mission_complete(e, completion_future),
            )
        else:
            sub = None

        # Start the mission via the orchestrator
        result = await self.orchestrator.start_mission(
            research_question=research_question,
            context=context,
        )

        if wait_for_completion:
            try:
                # Wait for the mission to complete (with timeout)
                report = await asyncio.wait_for(completion_future, timeout=timeout)
                self._logger.info(
                    "crew_mission_completed",
                    mission_id=result.get("mission_id"),
                    elapsed=report.get("elapsed"),
                )
                return {"status": "completed", "report": report}
            except asyncio.TimeoutError:
                self._logger.warning(
                    "crew_mission_timeout",
                    mission_id=result.get("mission_id"),
                    timeout=timeout,
                )
                return {"status": "timeout", "mission_id": result.get("mission_id")}
            finally:
                if sub:
                    self._event_bus.unsubscribe(sub)

        return {"status": "started", "mission_id": result.get("mission_id")}

    async def _on_mission_complete(
        self,
        event: Any,  # SystemEvent
        future: asyncio.Future[dict[str, Any]],
    ) -> None:
        """Handle the mission.completed event and resolve the waiting future."""
        if not future.done():
            future.set_result(event.payload)

    async def get_crew_status(self) -> dict[str, Any]:
        """Return the current status of all agents in the crew."""
        agent_statuses: list[dict[str, Any]] = []
        for agent in self._agents:
            meta = self._registry.get(agent.agent_id)
            agent_statuses.append({
                "agent_id": agent.agent_id[:12],
                "name": agent.name,
                "role": agent.role,
                "initialized": agent.is_initialized,
                "registry_status": meta.status if meta else "unknown",
                "uptime_seconds": round(agent.uptime, 1),
            })

        return {
            "crew_initialized": self._initialized,
            "agent_count": len(self._agents),
            "agents": agent_statuses,
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    def __repr__(self) -> str:
        status = "initialized" if self._initialized else "not initialized"
        return (
            f"DiscoveryCrew({len(self._agents)} agents, {status}, "
            f"agents={[a.name for a in self._agents]})"
        )
