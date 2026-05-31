#!/usr/bin/env python3
"""Substrate CLI — run simulations and launch curiosity swarm investigations.

Usage::

    substrate explore "Resolve the Hubble tension"
    substrate explore --list
    substrate explore --template hubble_tension
"""

from __future__ import annotations

import sys


def main() -> None:
    """Main entry point for the substrate CLI.

    Dispatches to subcommands::

        substrate explore <question>   # Launch a curiosity swarm investigation
    """
    if len(sys.argv) < 2:
        print("Usage: substrate explore <research-question>")
        print("       substrate explore --list")
        print("       substrate explore --template <template>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "explore":
        # Delegate to the research explore script
        from research.scripts.explore import main as explore_main

        sys.argv = sys.argv[1:]  # remove 'substrate' from args
        explore_main()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: explore")
        sys.exit(1)


if __name__ == "__main__":
    main()
