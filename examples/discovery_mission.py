#!/usr/bin/env python3
"""Example: Launch a Discovery Swarm mission for a real hard science problem.

This demonstrates the full end-to-end discovery workflow:

    1. Orchestrator decomposes the question
    2. Literature Scout surveys existing knowledge
    3. Hypothesis Forge generates candidate ideas
    4. CriticalReviewer + SimulationEngineer + UncertaintyQuantifier run in parallel
    5. Synthesis Architect delivers ranked proposals

Run with:
    python examples/discovery_mission.py
    substrate launch-discovery-mission --question "Design a promising new room-temperature superconductor candidate"
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def main() -> None:
    """Run a discovery mission and save the report."""
    # Pick your hard science question:
    questions = {
        "1": "Design a promising new room-temperature superconductor candidate",
        "2": "Identify novel catalyst materials for efficient ammonia synthesis at ambient conditions",
        "3": "Propose a mechanism for high-capacity solid-state hydrogen storage at room temperature",
    }

    print("\nAvailable discovery missions:\n")
    for key, question in questions.items():
        print(f"  [{key}] {question[:70]}...")

    choice = input("\nSelect mission [1-3, or enter custom question]: ").strip()
    if choice in questions:
        question = questions[choice]
    elif choice:
        question = choice
    else:
        question = questions["1"]

    print(f"\n{'='*60}")
    print(f"  LAUNCHING DISCOVERY MISSION")
    print(f"{'='*60}")
    print(f"  Question: {question}")
    print(f"{'='*60}\n")

    # Create and run the mission
    from research.discovery_swarm import DiscoveryMission

    mission = DiscoveryMission(
        question=question,
        max_parallel_workers=3,  # run critique/simulation/uncertainty in parallel
        verbose=True,
    )

    report = await mission.run()

    # Save the report
    report_path = report.save()
    print(f"\nFull mission report saved to: {report_path}")
    print(f"File size: {report_path.stat().st_size / 1024:.1f} KB")

    # Show a preview of the proposals
    if report.final_proposals:
        print(f"\nTop Proposal:")
        top = report.final_proposals[0]
        print(f"  Rank {top.get('rank', '?')}: {top.get('title', 'Untitled')[:80]}")
        print(f"  Confidence: {top.get('confidence', 'N/A')}")
        print(f"  Next step: {top.get('recommended_next_step', 'N/A')}")

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
