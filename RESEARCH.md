# Research Methodology

This document defines the evidence standards, research questions, experimental protocols, and measurement framework for the Substrate simulation platform. All claims about emergent behavior must be grounded in the quantitative metrics defined here.

## What Counts as Evidence

Valid evidence consists of statistically significant deviations from null model expectations on the following metrics:

### specialization_index

- **Definition**: Normalized entropy of the task-role distribution across agents.
- **Formula**: `H(p) / log(k)` where `H(p) = -sum(p_i * log(p_i))` over `k` roles and `p_i` is the proportion of agents assigned role `i`.
- **Range**: `[0, 1]`. 0 = all agents perform same role; 1 = uniform distribution across all roles.
- **Interpretation**: A value significantly above the null expectation (random role assignment) indicates that agents are developing distinct specializations rather than behaving homogeneously.

### communication_entropy

- **Definition**: Shannon entropy of the message type distribution over a sliding window of N ticks.
- **Formula**: `H(M) = -sum(m_i * log(m_i))` where `m_i` is the proportion of messages of type `i`.
- **Range**: `[0, log(k)]` for `k` message types.
- **Interpretation**: Increasing entropy suggests diversification of communication. Decreasing entropy suggests convergence on a few message types.

### tool_adoption_rate

- **Definition**: Parameters of a sigmoid curve fitted to cumulative tool adoption over time: `f(t) = L / (1 + exp(-k(t - t0)))`.
- **Parameters**: `L` (ceiling), `k` (growth rate), `t0` (inflection point).
- **Interpretation**: Growth rate `k` measures diffusion speed. Ceiling `L` measures ultimate penetration. An `L` significantly below population size indicates incomplete diffusion.

### memory_persistence_rate

- **Definition**: Fraction of memories surviving past a configurable age threshold `T` (default: 1000 ticks).
- **Formula**: `MPR(T) = count(memories with age > T) / count(all memories created at least T ticks ago)`.
- **Interpretation**: High MPR indicates effective memory retention mechanisms. Low MPR indicates memories decay before they can influence behavior across generations.

### lineage_survival_rate

- **Definition**: Fraction of agent lineages surviving past N generations.
- **Formula**: `LSR(N) = count(lineages with depth >= N) / count(all lineages started)`.
- **Interpretation**: Survival curves can be compared to exponential decay null model. Deviation from exponential decay (e.g., heavy tails) suggests evolved robustness.

### trade_network_density

- **Definition**: Ratio of actual trade relationships to maximum possible in a complete directed graph.
- **Formula**: `D = |E| / (|V| * (|V| - 1))` where `|E|` = number of directed trade edges and `|V|` = number of agents.
- **Range**: `[0, 1]`.
- **Interpretation**: Low density with high clustering suggests localized exchange networks. High density suggests open trade economy.

### reputation_convergence

- **Definition**: Variance of reputation scores across agents over time.
- **Formula**: `Var(R_t)` where `R_t` is the vector of all agent reputations at tick `t`.
- **Interpretation**: Decreasing variance over time indicates convergence toward consensus. Variance that remains high or oscillates indicates disagreement or instability.

## Research Questions

### RQ1: Under what conditions do agents specialize?

**Hypothesis**: Agents will develop measurable specialization when resource scarcity or heterogeneity creates comparative advantage.

**Predictions**:
- `specialization_index` will increase with resource heterogeneity.
- `specialization_index` will increase with population size (more opportunities for niche partitioning).
- `specialization_index` will remain near baseline under uniform resource conditions.

**Test**: Compare `specialization_index` across configurations with varying resource heterogeneity levels. Minimum 10 replicates per condition. Permutation test for significance.

### RQ2: Do cooperative strategies emerge without explicit rewards?

**Hypothesis**: Cooperative strategies (resource sharing, mutual defense) can emerge and stabilize when agents interact repeatedly and have memory of past interactions.

**Predictions**:
- `reputation_convergence` will decrease (variance decreases as consensus forms).
- Trade volume will be higher between agents with positive reputations.
- Alliances will form preferentially between agents with aligned reputations.

**Test**: Long-duration runs (>10,000 ticks). Compare reputation alignment and trade patterns against null model where agents interact randomly.

### RQ3: How do tools diffuse through a population?

**Hypothesis**: Tool diffusion follows an S-shaped (sigmoid) adoption curve, with diffusion speed modulated by social network structure.

**Predictions**:
- `tool_adoption_rate` will follow sigmoid curve with characteristic growth rate `k`.
- Higher social connectivity increases `k`.
- Tools with greater effect size have higher ceiling `L`.

**Test**: Track individual tool adoption over time. Fit sigmoid curves. Compare parameters across tool effectiveness levels and social network configurations.

### RQ4: What drives memory persistence across generations?

**Hypothesis**: Memories that are frequently accessed and reinforced persist longer. Inheritance creates lineage-specific knowledge traditions.

**Predictions**:
- `memory_persistence_rate` increases with memory access frequency.
- Lineages with higher `memory_persistence_rate` have higher `lineage_survival_rate`.
- Semantic memories persist longer than episodic memories.

**Test**: Track memory survival curves by type (episodic vs. semantic) and by lineage. Compare persistence distributions against null model (random forgetting).

### RQ5: Can persistent knowledge traditions form?

**Hypothesis**: Knowledge traditions (persistent tool-use patterns, social norms) can be transmitted across generations and maintain coherence over hundreds of generations.

**Predictions**:
- `tool_adoption_rate` will show sustained ceiling `L` across generations, not decaying to zero.
- `communication_entropy` will cluster around characteristic values per lineage.
- Tool-use patterns will cluster by lineage more than by environment.

**Test**: Analyze tool adoption and communication patterns across lineages. Compare within-lineage and between-lineage variance. Cluster analysis for tradition identification.

## Experimental Protocol

### Default Configuration

```toml
[simulation]
tick_rate = 10  # Hz
max_ticks = 100000
random_seed = 42

[world]
width = 100
height = 100
resource_types = ["food", "mineral", "water"]
resource_density = 0.3
regeneration_rate = 0.01

[agent]
initial_population = 50
cognitive_capacity = 10  # bits
energy_efficiency = 0.5
social_affinity = 0.3  # probability of initiating social interaction
mutation_rate = 0.01

[memory]
episodic_capacity = 1000
semantic_capacity = 500
decay_rate = 0.001
inheritance_fraction = 0.3

[economy]
initial_energy = 100.0
energy_decay_rate = 0.01
trade_enabled = true

[tools]
mutation_rate = 0.05
adoption_cost = 5.0  # energy units
initial_tools = 5

[persistence]
checkpoint_interval = 1000
wal_mode = true
```

### Intervention Types

| Intervention | Description | Config Parameter |
|-------------|-------------|-----------------|
| Resource Shock | Sudden depletion/replenishment of a resource | `intervention.resource_shock` |
| Agent Removal | Targeted removal of a fraction of agents | `intervention.agent_removal` |
| Tool Ban | Forced abandonment of a specific tool | `intervention.tool_ban` |
| Migration Wave | Sudden influx of new agents | `intervention.migration_wave` |
| Climate Shift | Gradual change in resource distribution | `intervention.climate_shift` |

### Data Collection

Per run, the platform collects:

- **Tick-level metrics**: All metrics listed above, recorded every N ticks (configurable, default: every 10)
- **Event log**: Every event on the event bus, serialized to Parquet
- **Agent snapshots**: Full agent state at configurable intervals
- **Configuration**: Complete configuration bundled with results

### Replication

Each experiment must:

1. Use fixed random seed recorded in configuration
2. Run minimum 10 replicates with different seeds
3. Record code version (git commit hash) with results
4. Bundle analysis scripts with data

A replication package consists of:
```
experiment/
  config.toml
  seeds.txt
  results/
    run_001/
    run_002/
    ...
  analysis/
    compute_metrics.py
    figures/
    summary_stats.json
  build_info.json  # git hash, dependencies, platform
```

## Measurement Framework

### What to Measure

| Metric | Symbol | When | Granularity |
|--------|--------|------|-------------|
| Specialization Index | `S` | Every 10 ticks | Global |
| Communication Entropy | `H_c` | Every 10 ticks | Global |
| Tool Adoption Rate | `k, L, t0` | Per tool, at end of run | Per tool |
| Memory Persistence Rate | `MPR` | Every 1000 ticks | Global, per lineage |
| Lineage Survival Rate | `LSR` | Every 1000 ticks | Per lineage |
| Trade Network Density | `D` | Every 100 ticks | Global |
| Reputation Convergence | `Var(R)` | Every 100 ticks | Global |

### How to Measure

All measurements are computed by the metrics module (`substrate.metrics`) from the event log and periodic state snapshots. The module is designed to be run both online (during simulation) and offline (on saved data) for identical results.

```python
# Example: computing specialization index
from substrate.metrics import compute_specialization_index

# Online: during simulation
specialization = compute_specialization_index(runtime.get_role_counts())

# Offline: from saved data
specialization = compute_specialization_index(role_counts_from_snapshot)
```

### Expected Patterns Under Null Hypothesis

| Metric | Null Expectation | Null Model |
|--------|-----------------|------------|
| Specialization Index | ~0.5 (uniform random assignment) | Random permutation of roles |
| Communication Entropy | ~log(k/2) (uniform message types) | Random message selection |
| Tool Adoption Rate | k ≈ 0 (no diffusion), L ≈ 1 | Random adoption model |
| Memory Persistence Rate | Exponential decay with half-life = 1/decay_rate | Pure random forgetting |
| Lineage Survival Rate | Exponential decay | Neutral drift model |
| Trade Network Density | Proportional to random encounter rate | Random pairing |
| Reputation Convergence | Random walk | No-reputation update model |

### What Would Constitute a Positive Result

A positive result requires:

1. **Statistical significance**: p < 0.01 (permutation test against null model)
2. **Effect size**: Cohen's d > 0.5 or equivalent
3. **Replicability**: Effect observed in at least 8 of 10 replicates
4. **Direction consistency**: Effect direction matches prediction across replicates
5. **No confound**: Effect not explained by trivial causes (e.g., population size differences)

Results that meet these criteria will be reported as "supported by evidence." Results that meet criteria 1-4 but not 5 will be reported as "preliminary, requires further investigation." Everything else is "not supported."
