#!/usr/bin/env python3
"""CLI entry point: ``substrate explore <research-question>``.

Launches a curiosity swarm investigation on the Substrate runtime.

Usage::

    # Minimal (3-agent swarm)
    substrate explore "Resolve the Hubble tension"

    # Full 7-agent swarm with custom config
    substrate explore "Map dark matter distribution" --team-size 7 --max-ticks 20 --output ./results

    # List available investigation templates
    substrate explore --list

    # Run a specific investigation template
    substrate explore --template hubble_tension
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="substrate explore",
        description="Launch a curiosity swarm scientific investigation on the Substrate runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  substrate explore \"Resolve the Hubble tension\"\n"
            "  substrate explore \"Map dark matter distribution\" --team-size 7\n"
            "  substrate explore --list\n"
            "  substrate explore --template hubble_tension\n"
        ),
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Research question to investigate (e.g., 'Resolve the Hubble tension')",
    )
    parser.add_argument(
        "--team-size",
        type=str,
        default="3-agent",
        choices=["3-agent", "7-agent"],
        help="Number of agent roles in the curiosity swarm (default: 3-agent)",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=10,
        help="Maximum investigation rounds (default: 10)",
    )
    parser.add_argument(
        "--template",
        type=str,
        choices=["hubble_tension", "dark_matter", "protein_folding"],
        help="Run a predefined investigation template",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available investigation templates",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for investigation report (default: research/curiosity_swarm/reports/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed tick-by-tick progress",
    )
    return parser


def list_templates() -> None:
    """Print available investigation templates."""
    templates = {
        "hubble_tension": "Resolve the Hubble constant tension between early and late universe measurements",
        "dark_matter": "Map dark matter distribution from galaxy rotation curve kinematics",
        "protein_folding": "Predict protein tertiary structure from amino acid sequence",
    }
    print("\nAvailable investigation templates:\n")
    for name, desc in templates.items():
        print(f"  {name:<20} {desc}")
    print()


async def run_investigation(args: argparse.Namespace) -> None:
    """Run the investigation based on CLI args."""
    from research.curiosity_swarm import CuriositySwarm
    from research.curiosity_swarm.roles import describe_team, get_team

    if args.list:
        list_templates()
        return

    # Determine research question
    question = args.question
    if args.template:
        templates = {
            "hubble_tension": "Resolve the Hubble tension between early and late universe measurements",
            "dark_matter": "Map dark matter distribution from galaxy rotation curve kinematics",
            "protein_folding": "Predict protein tertiary structure from amino acid sequence",
        }
        question = templates.get(args.template, question or args.template)

    if not question:
        print("Error: Provide a research question or use --template / --list")
        sys.exit(1)

    # Create the swarm
    swarm = CuriositySwarm(
        team_size=args.team_size,
        max_ticks=args.max_ticks,
        output_dir=args.output or "research/curiosity_swarm/reports",
    )

    team = get_team(args.team_size)
    print(f"\n{'='*60}")
    print(f"  Substrate Curiosity Swarm")
    print(f"  Team: {args.team_size} ({len(team)} agents)")
    print(f"  Question: {question}")
    print(f"  Max ticks: {args.max_ticks}")
    print(f"{'='*60}\n")
    print(f"Roles:")
    for i, role in enumerate(team, 1):
        print(f"  {i}. {role.name}: {role.description}")
    print()

    # Run the investigation
    print("Starting investigation...\n")
    report = await swarm.investigate(question)

    # Save and print report
    report_path = report.save(args.output)
    print(f"\nInvestigation complete in {report.duration_seconds:.1f}s")
    print(f"Total ticks: {report.total_ticks}")
    print(f"Report saved: {report_path}")

    if args.verbose:
        print(f"\n{'='*60}")
        print("  INVESTIGATION REPORT")
        print(f"{'='*60}\n")
        print(report.conclusion)
        print(f"\nConfidence: {report.confidence}")
        if report.open_questions:
            print(f"\nOpen questions:")
            for q in report.open_questions:
                print(f"  - {q}")


async def run_template_investigation(template_name: str) -> dict[str, Any]:
    """Run a predefined investigation template programmatically."""
    from research.curiosity_swarm.experiments import (
        HubbleTensionInvestigation,
        DarkMatterInvestigation,
        ProteinFoldingInvestigation,
    )

    templates = {
        "hubble_tension": HubbleTensionInvestigation,
        "dark_matter": DarkMatterInvestigation,
        "protein_folding": ProteinFoldingInvestigation,
    }

    if template_name not in templates:
        msg = f"Unknown template '{template_name}'. Choose from: {list(templates.keys())}"
        raise ValueError(msg)

    investigation = templates[template_name]()
    results = await investigation.run()
    return results


def main() -> None:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        list_templates()
        return

    asyncio.run(run_investigation(args))


if __name__ == "__main__":
    main()
