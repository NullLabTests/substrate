# Substrate

**A persistent multi-agent civilization experiment exploring the emergence of collective intelligence.**

Substrate is a tick-based async simulation runtime for persistent AI agent civilizations. Agents live, communicate, trade, form alliances, create tools, reproduce, evolve, and die — all within a simulated world that persists across runs and survives crashes.

## Core Premise

Give agents sparse goals, a persistent world, and the ability to interact, then observe what structures emerge. No hardcoded social rules, no prescribed outcomes — just substrate.

## Quick Start

```bash
pip install -e ".[dev]"
pytest -v
```

## Project Structure

```
substrate/
  core/          — Simulation runtime, event bus, agent registry
  civilization/  — Agent model, world state, environment
  memory/        — Episodic, semantic, aging, inheritance
  economy/       — Resources, trade, energy, scarcity
  evolution/     — Reproduction, mutation, lineage, selection
  tools/         — Tool creation, adoption, abandonment
  social/        — Messaging, alliances, reputation
  observatory/   — Metrics, analysis, visualization
  docs/          — Guides, specifications
  tests/         — Unit, integration, e2e
```

## Milestones

| # | Milestone | Focus |
|---|-----------|-------|
| M1 | Foundation | Runtime, event bus, persistence, recovery |
| M2 | Persistent Agents | Agent lifecycle, memory systems |
| M3 | Social Systems | Messaging, alliances, reputation, telemetry |
| M4 | Evolution | Reproduction, mutation, tool innovation |
| M5 | Observatory | Civilization-scale metrics & analysis |
| M6 | Long-Horizon Experiments | Multi-day runs, interventions, replication |

## Research Questions

1. Under what conditions do agents specialize?
2. Do cooperative strategies emerge without explicit rewards?
3. How do tools diffuse through a population?
4. What drives memory persistence across generations?
5. Can persistent knowledge traditions form?

See [RESEARCH.md](RESEARCH.md) for methodology and evidence standards.

## License

MIT
