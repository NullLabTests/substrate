# Architecture

## System Overview

The platform is organized as a layered architecture. Each layer provides well-defined interfaces to the layer above and depends on services from the layer below.

```
                   ┌─────────────────────────────────────────────┐
                   │           Telemetry & Logging                │
                   │  (metrics export, structured logging,       │
                   │   trace collection, dashboards)              │
                   └─────────────────────────────────────────────┘
                                     │
   ┌─────────────────────────────────┼─────────────────────────────────┐
   │              │                  │                  │              │
   │  ┌───────────┴──────────┐  ┌───┴────────────┐  ┌──┴───────────┐  │
   │  │   Civilization       │  │   Economy       │  │   Social     │  │
   │  │   • Agent model      │  │   • Energy      │  │   • Messages │  │
   │  │   • World state      │  │   • Resources   │  │   • Alliances│  │
   │  │   • Environment      │  │   • Trade       │  │   • Rep      │  │
   │  └──────────────────────┘  └─────────────────┘  └─────────────┘  │
   │                    │                    │                         │
   │  ┌─────────────────┴────────────────────┴──────────────────┐     │
   │  │                    Memory Systems                        │     │
   │  │      (episodic, semantic, aging, inheritance)            │     │
   │  └──────────────────────────────────────────────────────────┘     │
   │                    │                    │                         │
   │  ┌─────────────────┴────────────────────┴──────────────────┐     │
   │  │   Evolution Layer     │        Tools Layer               │     │
   │  │   • Reproduction      │        • Creation                │     │
   │  │   • Mutation          │        • Adoption                │     │
   │  │   • Lineage           │        • Mutation                │     │
   │  │   • Selection         │        • Lineage tracking        │     │
   │  └───────────────────────┴──────────────────────────────────┘     │
   └─────────────────────────────────┬─────────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │           Event Bus             │
                     │  (pub/sub, topics, ordering,    │
                     │   replay, delivery guarantees)  │
                     └───────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │         Runtime Layer           │
                     │  • Tick scheduler               │
                     │  • Agent lifecycle              │
                     │  • Agent registry               │
                     │  • Recovery coordinator          │
                     └───────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │       Persistence Layer        │
                     │  (SQLite, WAL mode,           │
                     │   migrations, checkpointing)   │
                     └───────────────────────────────┘
```

## Runtime Layer

### Purpose

The runtime layer owns the simulation loop, agent lifecycle, and tick scheduling. It is the entry point for all simulation execution.

### Key Interface

```python
class Runtime:
    def __init__(self, config: RuntimeConfig, persistence: PersistenceBackend):
        ...

    async def run(self, max_ticks: int | None = None) -> RunResult:
        ...

    async def resume(self, checkpoint_id: str) -> RunResult:
        ...

    async def pause(self) -> Checkpoint:
        ...

    async def shutdown(self) -> Checkpoint:
        ...
```

### Tick Loop

The tick loop operates at a configurable tick rate (default: 10 Hz). Each tick:

1. **Pre-tick**: Persistence health check, clock synchronization
2. **Agent processing**: Each active agent receives a time slice (configurable, default proportional to agent energy)
3. **World step**: Environment update (resource regeneration, decay processes)
4. **Event flush**: All pending events delivered
5. **Post-tick**: Metrics collection, checkpoint decision (configurable interval)

### Lifecycle States

```
SPAWNED → ACTIVE → SUSPENDED → ACTIVE → TERMINATED
                      ↓                        ↑
                   ARCHIVED ────────────────────┘
```

## Event Bus

### Purpose

Central communication backbone. All inter-component communication passes through the event bus. This enables replay, auditing, and decoupled architecture.

### Topics

| Topic | Publishers | Subscribers | Schema |
|-------|-----------|-------------|--------|
| `agent.spawn` | Registry | Civilization, Persistence | `{agent_id, traits, tick}` |
| `agent.act` | Runtime | Civilization, Memory, Persistence | `{agent_id, action, result, tick}` |
| `agent.die` | Runtime | Registry, Evolution, Persistence | `{agent_id, cause, tick}` |
| `social.message` | Social | Memory, Telemetry | `{from, to, content, tick}` |
| `social.alliance` | Social | Reputation, Telemetry | `{agents, terms, tick}` |
| `economy.trade` | Economy | Social, Memory, Telemetry | `{from, to, resource, quantity, tick}` |
| `tool.create` | Tools | Registry, Evolution, Telemetry | `{agent_id, tool_id, parent, tick}` |
| `tool.adopt` | Tools | Registry, Telemetry | `{agent_id, tool_id, tick}` |
| `tool.abandon` | Tools | Registry, Telemetry | `{agent_id, tool_id, tick}` |

### Replay

Event bus supports full replay from any checkpoint. Replay mode delivers events in order without dispatching to external systems (pure computation). Used for deterministic re-analysis.

## Agent Registry

### Purpose

Central repository of all agent identities and their current lifecycle state. Provides lookup, enumeration, and state transition operations.

### Data Flow

```
Spawn request → Registry validates → Registry assigns ID → Registry emits agent.spawn → Components initialize agent state
```

### Key Operations

- `register(agent_data) -> AgentID`
- `unregister(agent_id) -> None`
- `get(agent_id) -> AgentRecord`
- `list(state_filter=None) -> list[AgentRecord]`
- `transition(agent_id, new_state) -> None`

## Persistence Layer

### Purpose

Ensures simulation state survives process termination. Uses SQLite with WAL mode for concurrent read access during writes.

### Implementation

- **Backend**: SQLite via `sqlite3` with WAL journal mode
- **Checkpointing**: Full state snapshots at configurable tick intervals; incremental delta logs between checkpoints
- **Migrations**: Schema version tracked in `_schema_version` table; migrations applied automatically on open
- **Recovery**: On restart, locate most recent valid checkpoint, apply deltas, verify checksum

### Schema

```
agents
  id TEXT PRIMARY KEY
  state TEXT NOT NULL
  traits BLOB
  created_tick INTEGER
  last_active_tick INTEGER

events
  id INTEGER PRIMARY KEY AUTOINCREMENT
  topic TEXT NOT NULL
  payload BLOB NOT NULL
  tick INTEGER NOT NULL
  ordering INTEGER NOT NULL

checkpoints
  id TEXT PRIMARY KEY
  tick INTEGER NOT NULL
  snapshot BLOB NOT NULL
  checksum TEXT NOT NULL
  created_at TEXT NOT NULL

deltas
  id INTEGER PRIMARY KEY AUTOINCREMENT
  checkpoint_id TEXT NOT NULL
  tick INTEGER NOT NULL
  operations BLOB NOT NULL
```

## Civilization Layer

### Purpose

Models the agent-level world state: agent traits, environment conditions, resource distribution, and the rules governing agent-environment interaction.

### Agent Model

Each agent possesses:

- **Traits**: Fixed parameters set at spawn (cognitive capacity, energy efficiency, social affinity, mutation rate)
- **State**: Dynamic variables (energy level, position, skills, active tools, inventory, alliances)
- **Memory**: Collection of episodic and semantic memories (see Memory Systems)

### World Simulation

- **Environment**: Grid-based or abstract topology (configurable). Resources regenerate at configurable rates.
- **Time**: Discrete ticks. Each tick represents a fixed duration (default: 1 second of simulated time).
- **Dynamics**: Resource consumption, energy decay, environmental events (resource booms, scarcity periods).

## Memory Systems

### Purpose

Provide agents with the ability to store, retrieve, and inherit information across their lifetime and across generations.

### Memory Types

- **Episodic**: Timestamped records of events the agent experienced. Bounded capacity (oldest evicted first).
- **Semantic**: Extracted knowledge from episodic memories. Stores generalizations, rules, and learned associations.
- **Aging**: Memories decay in accessibility over time unless reinforced. Decay function is configurable.
- **Inheritance**: On reproduction, a configurable fraction of semantic memories passes to offspring. Episodic memories are not inherited.

### Interfaces

```python
class MemorySystem:
    def store_episodic(self, agent_id, event) -> MemoryID
    def store_semantic(self, agent_id, concept, strength) -> MemoryID
    def recall(self, agent_id, query, limit=10) -> list[Memory]
    def age_all(self, tick) -> None
    def inherit(self, parent_id, child_id) -> int  # returns count of inherited memories
```

## Economy

### Purpose

Governs resource production, consumption, exchange, and scarcity. Provides the substrate for trade relationships and specialization pressure.

### Resources

- **Energy**: Universal resource required for agent operation. Consumed each tick. Earned through work or trade.
- **Materials**: Specific resources required for tool creation and certain actions. Heterogeneous distribution across environment.
- **Scarcity**: Resource availability varies spatially and temporally. Scarcity events (droughts, depletions) occur probabilistically.

### Trade

- Agents can propose bilateral trades. Each trade specifies resource type, quantity, and terms.
- Trade success depends on both parties agreeing and having sufficient resources.
- Trade history feeds into reputation system.

```python
class Economy:
    def transfer(self, from_id, to_id, resource, quantity) -> TradeResult
    def get_balance(self, agent_id, resource) -> float
    def get_market_price(self, resource) -> float
    def step(self, tick) -> None
```

## Social

### Purpose

Enables agent-to-agent communication, alliance formation, and reputation tracking.

### Messaging

- Directed messages between agents with content validation and rate limiting.
- Messages persist in the event log for replay and analysis.

### Alliances

- Bilateral agreements with optional terms (resource sharing, defense, information exchange).
- Alliances can be dissolved by either party.
- Alliance history feeds into reputation calculations.

### Reputation

- Reputation is a scalar value per agent (range: [-1, 1]).
- Updated based on observed actions: keeping agreements increases reputation; betrayals decrease it.
- Reputation affects trade willingness and alliance formation.

## Evolution

### Purpose

Manages reproduction, mutation, and lineage tracking. Provides the evolutionary dynamics that drive specialization and adaptation.

### Reproduction

- Agents meeting energy and age thresholds can reproduce.
- Offspring inherit a mutated copy of parent traits and a subset of semantic memories.
- Reproduction consumes energy from parent.

### Mutation

- Each trait mutates independently with configurable probability and effect size.
- Mutation rate can be inherited (enabling evolution of evolvability).

### Lineage

- Every agent has a `parent_id` (null for initial seed agents).
- Lineages are tracked in a tree structure for phylogenetic analysis.

```python
class Evolution:
    def can_reproduce(self, agent_id) -> bool
    def reproduce(self, agent_id) -> AgentID
    def get_lineage(self, agent_id) -> list[AgentID]
    def lineage_survival_rate(self, min_generations) -> float
```

## Tools

### Purpose

Models tool creation, adoption, and abandonment. Enables study of innovation diffusion.

### Tool Model

Each tool has:

- **Properties**: Effect size, energy cost, complexity, prerequisites
- **Lineage**: Parent tool (if created from existing tool)
- **Creator**: Agent ID of the creating agent
- **State**: Available (known but not used), Active (currently used), Lost (no current users)

### Creation

- Agents can create new tools by combining or modifying existing tools.
- Creation success depends on agent skills and tool complexity.
- Created tools may mutate relative to their parent(s).

### Adoption

- Tools spread through agent populations via observation and teaching.
- Adoption probability depends on tool effectiveness and agent social network proximity.
- Abandonment occurs when better tools appear or maintenance costs exceed benefits.

```python
class ToolSystem:
    def create(self, agent_id, name, properties) -> ToolID
    def adopt(self, agent_id, tool_id) -> None
    def abandon(self, agent_id, tool_id) -> None
    def get_users(self, tool_id) -> set[AgentID]
    def diffusion_curve(self, tool_id) -> dict
```

## Telemetry & Logging

### Purpose

Collect, structure, and export all simulation events for analysis. Provides both real-time monitoring and post-hoc analysis capability.

### Output Formats

- **CSV**: Tabular event logs, one file per event type
- **JSON Lines**: Streaming JSON for real-time consumption
- **Parquet**: Columnar format for efficient analysis of large runs
- **Prometheus**: Real-time metrics via push gateway

### Logged Metrics (per tick)

- Agent count (total, active, suspended, terminated)
- Energy distribution (mean, median, p10, p90)
- Resource availability (by resource type)
- Trade volume (count, mean value)
- Message volume (sent, delivered)
- Tool count (total, active, new)
- Alliance count (active, formed, dissolved)
- Specialization index
- Communication entropy

## Recovery & Crash Resilience

### Purpose

Ensure that a simulation crash does not lose more than a configurable amount of work.

### Mechanism

1. **Periodic checkpoints**: Full state snapshots at configurable tick intervals (default: every 1000 ticks)
2. **Delta logs**: Between checkpoints, each tick's state changes are recorded as deltas
3. **Recovery flow**:
   - On restart, scan for most recent valid checkpoint
   - Verify checkpoint checksum
   - Apply deltas in order up to last complete tick
   - Resume simulation from that tick

### Guarantees

- At most `checkpoint_interval + 1` ticks of work lost on crash
- Checkpoint writes are atomic (SQLite transaction)
- Recovery is verified by checksum comparison
- Failed recovery falls back to previous valid checkpoint
