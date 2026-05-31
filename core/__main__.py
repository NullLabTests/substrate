#!/usr/bin/env python3
"""Substrate CLI — simulation runtime, curiosity swarm, and discovery missions.

Usage::

    substrate explore "Resolve the Hubble tension"
    substrate explore --list
    substrate launch-discovery-mission --question "Design a new superconductor"
    substrate launch-discovery-mission --interactive
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="substrate",
        description="Tick-based async simulation runtime for persistent AI agent civilizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- explore ---
    explore_parser = subparsers.add_parser(
        "explore",
        help="Launch a curiosity swarm scientific investigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    explore_parser.add_argument(
        "question",
        nargs="?",
        help="Research question to investigate",
    )
    explore_parser.add_argument("--team-size", type=str, default="3-agent", choices=["3-agent", "7-agent"])
    explore_parser.add_argument("--max-ticks", type=int, default=10)
    explore_parser.add_argument("--template", type=str, choices=["hubble_tension", "dark_matter", "protein_folding"])
    explore_parser.add_argument("--list", action="store_true", help="List available investigation templates")
    explore_parser.add_argument("--output", type=str, default=None)
    explore_parser.add_argument("--verbose", action="store_true")

    # --- launch-discovery-mission ---
    mission_parser = subparsers.add_parser(
        "launch-discovery-mission",
        help="Launch a full 7-agent discovery mission for hard science problems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  substrate launch-discovery-mission --question \"Design a superconductor\"\n"
            "  substrate launch-discovery-mission --question \"Catalyst for ammonia synthesis\"\n"
            "  substrate launch-discovery-mission --interactive\n"
        ),
    )
    mission_parser.add_argument(
        "--question", "-q",
        type=str,
        default=None,
        help="Research question for the discovery mission",
    )
    mission_parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Select from predefined mission templates interactively",
    )
    mission_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output path for the mission report",
    )
    mission_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Print detailed progress",
    )
    mission_parser.add_argument(
        "--parallel-workers",
        type=int,
        default=3,
        help="Number of parallel workers for evaluation phase (default: 3)",
    )

    return parser


def main() -> None:
    """Main entry point — dispatches to subcommands."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "explore":
        from research.scripts.explore import run_investigation, list_templates

        if args.list:
            list_templates()
            return

        if not args.question and not args.template:
            parser.parse_args(["explore", "--help"])
            return

        import asyncio
        asyncio.run(run_investigation(args))

    elif args.command == "launch-discovery-mission":
        _launch_discovery_mission(args)

    else:
        parser.print_help()
        sys.exit(1)


def _launch_discovery_mission(args: argparse.Namespace) -> None:
    """Launch a 7-agent discovery mission."""
    import asyncio

    question = args.question

    if args.interactive or not question:
        # Interactive mode: show predefined questions
        questions = {
            "1": "Design a promising new room-temperature superconductor candidate",
            "2": "Identify novel catalyst materials for efficient ammonia synthesis at ambient conditions",
            "3": "Propose a mechanism for high-capacity solid-state hydrogen storage at room temperature",
            "4": "Design a novel metamaterial with negative refractive index in the visible spectrum",
            "5": "Propose a mechanism for room-temperature quantum coherence in molecular systems",
        }

        print("\nSelect a discovery mission:\n")
        for key, q in questions.items():
            print(f"  [{key}] {q[:72]}...")

        if question and question not in questions.values():
            print(f"  [C] Custom: {question[:60]}...")
        print(f"  [C] Enter a custom question")

        choice = input("\nChoice [1-5 or C]: ").strip()
        if choice in questions:
            question = questions[choice]
        elif choice.upper() == "C":
            question = input("Enter your research question: ").strip()
        else:
            print("No valid selection. Using default mission.")
            question = questions["1"]

    if not question:
        print("Error: No research question provided.")
        sys.exit(1)

    from research.discovery_swarm import DiscoveryMission

    mission = DiscoveryMission(
        question=question,
        max_parallel_workers=args.parallel_workers,
        verbose=args.verbose,
    )

    report = asyncio.run(mission.run())

    report_path = report.save(args.output)
    print(f"\nReport saved: {report_path}")

    # Print final ranked proposals
    if report.final_proposals:
        print(f"\n{'='*60}")
        print("  RANKED PROPOSALS")
        print(f"{'='*60}")
        for i, p in enumerate(report.final_proposals, 1):
            print(f"\n  [{i}] {p.get('title', 'Untitled')[:80]}")
            print(f"      Confidence: {p.get('confidence', 'N/A')}")
            print(f"      Evidence:   {p.get('evidence_strength', 'N/A')}")
            print(f"      Next step:  {p.get('recommended_next_step', 'N/A')}")


if __name__ == "__main__":
    main()
