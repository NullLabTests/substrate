# Roadmap

## Phase 1: Persistent Agents

**Goal**: Establish the core simulation runtime that keeps agents alive and operating across ticks, survives crashes, and provides a foundation for all higher-layer features.

### Key Components

- **Simulation Runtime**: Tick-based main loop with configurable tick rate, pause/resume, and graceful shutdown.
- **Event Bus**: Publish-subscribe message bus with topic routing, delivery guarantees, and event replay capability.
- **Agent Registry**: Central registry tracking all agent identities, lifecycle state (spawned, alive, suspended, terminated), and metadata.
- **Tick Scheduler**: Deterministic tick distribution ensuring each agent receives processing time proportional to its capabilities.
- **SQLite Persistence**: Full state serialization to SQLite with Write-Ahead Logging (WAL mode) for crash recovery.
- **Recovery System**: Automatic state reconstruction on restart from last consistent checkpoint.

### Expected Deliverables

- `substrate.runtime` — core loop and scheduler
- `substrate.events` — event bus implementation
- `substrate.registry` — agent registry with lifecycle
- `substrate.persist` — SQLite persistence layer
- `substrate.recovery` — crash recovery subsystem
- CLI commands: `run`, `resume`, `status`
- Integration tests demonstrating >1000 agent ticks with full persistence round-trip

### Measurement Criteria

- Tick throughput (agents processed per second)
- Persistence write latency (p95 < 10ms per checkpoint)
- Recovery time (seconds to restore from last checkpoint)
- Event bus latency (p99 < 5ms event delivery)
- Memory footprint per agent (target < 1KB agent state)

### Timeline Estimate

8–10 weeks

---

## Phase 2: Social Systems

**Goal**: Enable agents to communicate, form alliances, and develop reputations, producing measurable social network structures.

### Key Components

- **Messaging System**: Directed message passing between agents with routing, delivery receipts, and rate limiting.
- **Alliance Framework**: Bilateral and multilateral agreements with terms, duration, and dissolution conditions.
- **Reputation Engine**: Event-driven reputation updates based on observed agent behavior, with decay over time.
- **Structured Logging**: JSON-format event logs with schema per event type for downstream analysis.
- **Telemetry Pipeline**: Metrics collection and export (Prometheus push gateway, CSV, Parquet).

### Expected Deliverables

- `substrate.social.messaging` — message transport
- `substrate.social.alliances` — alliance lifecycle
- `substrate.social.reputation` — reputation tracking
- `substrate.telemetry` — metrics pipeline
- Integration tests verifying alliance formation and reputation propagation

### Measurement Criteria

- Message delivery rate (messages/tick)
- Alliance formation frequency (alliances formed / agent-hour)
- Reputation convergence time (ticks to stabilize)
- Telemetry export throughput (events/second)
- Communication entropy (Shannon entropy of message patterns)

### Timeline Estimate

6–8 weeks

---

## Phase 3: Tool Evolution

**Goal**: Implement mechanisms for tool creation, adoption, and inheritance, enabling study of innovation diffusion.

### Key Components

- **Tool Creation**: Agents can create new tools from existing primitives, with random mutation and guided refinement.
- **Adoption Networks**: Graph tracking who uses which tools, how tools spread, and abandonment patterns.
- **Mutation Engine**: Tools can mutate during creation or inheritance, with configurable mutation rates and effect sizes.
- **Lineage Tracking**: Full ancestry for every tool, enabling phylogenetic analysis of innovation.

### Expected Deliverables

- `substrate.tools.creation` — tool generation
- `substrate.tools.adoption` — adoption/abandonment dynamics
- `substrate.tools.mutation` — mutation mechanics
- `substrate.tools.lineage` — ancestry tracking
- Diffusion curve analysis scripts

### Measurement Criteria

- Tool creation rate (tools created per tick)
- Adoption curve parameters (sigmoid fit: inflection point, growth rate, ceiling)
- Tool survival rate (fraction of tools surviving N ticks after creation)
- Mutation impact on adoption (effect size of mutations on adoption probability)
- Lineage depth distribution

### Timeline Estimate

6–8 weeks

---

## Phase 4: Civilization Metrics

**Goal**: Define, validate, and instrument quantitative metrics that capture civilization-scale properties.

### Key Components

- **Specialization Index**: Measure of task distribution skew across agents. Computed as the normalized entropy of agent-role assignments. Values near 1 indicate high specialization; values near 0 indicate generalist populations.
- **Communication Entropy**: Shannon entropy of the message type distribution. Measures diversity of communication patterns.
- **Tool Adoption Rates**: Sigmoid curve fitted to cumulative adoption over time. Parameters: midpoint, growth rate, ceiling.
- **Memory Persistence Rate**: Fraction of memories surviving past a configurable age threshold. Tracks knowledge retention across generations.
- **Lineage Survival Rate**: Fraction of agent lineages surviving past N generations. Measures evolutionary robustness.
- **Trade Network Density**: Ratio of actual trade relationships to maximum possible (complete graph).
- **Reputation Convergence**: Variance of reputation scores across agents over time. Converging variance indicates consensus.

### Expected Deliverables

- `substrate.metrics.specialization` — specialization index computation
- `substrate.metrics.entropy` — communication entropy
- `substrate.metrics.adoption` — tool adoption analysis
- `substrate.metrics.persistence` — memory persistence
- `substrate.metrics.lineage` — lineage survivorship
- `substrate.metrics.trade` — network density
- `substrate.metrics.reputation` — convergence metrics
- Metric visualization scripts

### Measurement Criteria

- Metric computation overhead (< 1% of tick time)
- Statistical test integration (permutation tests for significance)
- Metric stability under null conditions

### Timeline Estimate

4–6 weeks

---

## Phase 5: Long-horizon Experiments

**Goal**: Design, execute, and analyze multi-day civilization runs that generate statistically meaningful results.

### Key Components

- **Multi-day Run Infrastructure**: Scheduling, checkpointing, and monitoring for runs lasting 24–72 hours.
- **Intervention Studies**: Ability to inject controlled perturbations mid-run (resource shocks, agent removal, tool bans).
- **Replication Packages**: Full reproducibility — configuration, seed, code version, and analysis scripts bundled per experiment.
- **Analysis Pipeline**: Automated statistical analysis generating figures and summary statistics per run.

### Expected Deliverables

- Experiment framework with parameter sweeps
- Intervention injection system
- Replication package format (configuration + seed + commit hash + scripts)
- Published experiment results with analysis
- At least 3 distinct long-horizon studies

### Measurement Criteria

- Run stability (fraction of runs completing without crash)
- Intervention effect detection (statistical power analysis)
- Replication consistency (effect size variance across replicates)
- Analysis pipeline throughput (runs analyzed per hour)

### Timeline Estimate

8–12 weeks
