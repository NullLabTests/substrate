# Ownership

## Agent 1 — Infrastructure

**Owns:** `core/`, `memory/`, `tests/`, `pyproject.toml`

- Simulation runtime & tick scheduler
- Event bus & agent registry
- Persistence layer & crash recovery
- Memory systems (episodic, semantic, aging, inheritance)
- Build, test, and CI infrastructure

## Agent 2 — Civilization Systems

**Owns:** `civilization/`, `economy/`, `social/`, `evolution/`, `tools/`

- Agent model, world state, environment
- Economy: resources, trade, energy, scarcity
- Social: messaging, alliances, reputation
- Evolution: reproduction, mutation, lineage, selection
- Tools: creation, adoption, abandonment

## Agent 3 — Research & Documentation

**Owns:** `observatory/`, `docs/`, `research/`

- Metrics framework & computation
- Analysis pipelines & visualization
- Experiment design & replication packages
- All documentation: ARCHITECTURE.md, RESEARCH.md, ROADMAP.md, CONTRIBUTING.md

## PR Requirements

Every pull request must reference:

- **Purpose**: What problem does this solve?
- **Research value**: What question does this help answer?
- **Affected modules**: Which subsystems are touched?

## Change Review Matrix

| Change affects | Requires review from |
|---------------|---------------------|
| `core/*`, `memory/*` | Agent 1 |
| `civilization/*`, `economy/*`, `social/*`, `evolution/*`, `tools/*` | Agent 2 |
| `observatory/*`, `docs/*`, `research/*` | Agent 3 |
| Multiple domains | All affected owners |
| `pyproject.toml`, CI, cross-cutting | Agent 1 (lead) + relevant owners |
