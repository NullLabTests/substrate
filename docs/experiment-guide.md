# Experiment Guide

This document describes how to set up, run, and analyze experiments using the Substrate simulation platform.

## Prerequisites

- Python 3.11 or later
- Git
- 500 MB free disk space (for results storage)
- 4 GB RAM recommended for large simulations

## Basic Simulation Run

```bash
# Clone and install
git clone https://github.com/your-org/substrate.git
cd substrate
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run default simulation (50 agents, 100,000 ticks)
python -m substrate run --config configs/default.toml

# Run with custom tick limit
python -m substrate run --config configs/default.toml --ticks 50000
```

Expected output:
```
[INFO] Starting simulation run_2025-01-01_12-00-00
[INFO] Config: configs/default.toml
[INFO] Agent count: 50
[INFO] Tick rate: 10 Hz
[INFO] Max ticks: 100000
[PROGRESS] 0% [###---------------------] 10000/100000
...
[INFO] Run complete. Results in: runs/run_2025-01-01_12-00-00
```

## Configuring Parameters

Configuration uses TOML format. The default configuration is at `configs/default.toml`.

### Modifying Agent Population

```toml
[agent]
initial_population = 100   # Start with 100 agents
cognitive_capacity = 12    # Bits of information processing
mutation_rate = 0.02       # Per-trait mutation probability
```

### Modifying Environment

```toml
[world]
width = 200
height = 200
resource_types = ["food", "mineral", "water", "crystal"]
resource_density = 0.2     # 20% of cells have resources
regeneration_rate = 0.005  # Slower regeneration
```

### Modifying Economy

```toml
[economy]
initial_energy = 200.0     # Agents start with more energy
energy_decay_rate = 0.02   # Faster energy consumption
trade_enabled = true
trade_tax = 0.05           # 5% tax on trades
```

### Custom Configuration File

Create a new TOML file with only the parameters you want to override:

```toml
# configs/my_experiment.toml
[agent]
initial_population = 200
mutation_rate = 0.05

[memory]
inheritance_fraction = 0.5

[tools]
mutation_rate = 0.1
```

The platform merges your custom configuration with the defaults.

## Collecting Results

Results are stored in `runs/run_{timestamp}` directory:

```
runs/run_2025-01-01_12-00-00/
  config.toml                   # Full resolved configuration
  events/                       # Event logs
    agent.parquet
    social.parquet
    economy.parquet
    tools.parquet
  metrics/                      # Per-tick metrics
    specialization.csv
    entropy.csv
    adoption.csv
    persistence.csv
    lineage.csv
    trade.csv
    reputation.csv
  snapshots/                    # Full state snapshots
    tick_10000.json
    tick_20000.json
  summary.json                  # Run summary statistics
  build_info.json               # Code version and dependencies
```

To list completed runs:

```bash
python -m substrate list-runs
```

## Analyzing Telemetry

### Generate Summary Statistics

```bash
python -m substrate analyze --run-dir runs/run_2025-01-01_12-00-00
```

Output:
```
Run: run_2025-01-01_12-00-00
Ticks completed: 100000
Duration: 2h 47m 30s
Final agent count: 43
Lineages survived: 12 / 50
Tools created: 47
Total trades: 12834
Specialization index (final): 0.72
Communication entropy (final): 3.41 bits
```

### Plot Metrics

```bash
python -m substrate plot --run-dir runs/run_2025-01-01_12-00-00 --metrics specialization,entropy
```

Generates PNG plots in the run directory.

### Compare Runs

```bash
python -m substrate compare runs/run_2025-01-01_12-00-00 runs/run_2025-01-02_12-00-00
```

## Reproducing Experiments

Each run records its full configuration and code version. To reproduce a run:

```bash
# Check out the same code version
git checkout $(jq -r .commit_hash runs/run_2025-01-01_12-00-00/build_info.json)

# Re-run with identical configuration
python -m substrate run --config runs/run_2025-01-01_12-00-00/config.toml
```

The platform respects the random seed in the configuration, so re-running with the same seed produces identical results.

### Running a Replication Set

```bash
# Run 10 replicates with different seeds
python -m substrate experiment --config configs/default.toml --replicates 10

# Results in: experiments/experiment_{timestamp}/
#   run_001/
#   run_002/
#   ...
#   run_010/
#   aggregate/
```

## Example Experiment Walkthrough

### Experiment: Does resource heterogeneity increase specialization?

**Research Question**: RQ1 — Under what conditions do agents specialize?

**Prediction**: `specialization_index` will increase with resource heterogeneity.

**Protocol**:

1. Create three configuration variants:

```bash
# uniform.toml - identical resource distribution
cat > configs/uniform.toml << 'EOF'
[world]
resource_types = ["food"]
resource_density = 0.5
regeneration_rate = 0.01
seed = 42
EOF

# moderate.toml - multiple resource types, moderate clustering
cat > configs/moderate.toml << 'EOF'
[world]
resource_types = ["food", "mineral"]
resource_density = 0.3
regeneration_rate = 0.01
seed = 42
EOF

# heterogeneous.toml - many resource types, sparse distribution
cat > configs/heterogeneous.toml << 'EOF'
[world]
resource_types = ["food", "mineral", "water", "crystal", "lumber"]
resource_density = 0.15
regeneration_rate = 0.005
seed = 42
EOF
```

2. Run 10 replicates of each condition:

```bash
python -m substrate experiment --config configs/uniform.toml --replicates 10
python -m substrate experiment --config configs/moderate.toml --replicates 10
python -m substrate experiment --config configs/heterogeneous.toml --replicates 10
```

3. Aggregate results:

```bash
python -m substrate aggregate --experiment-dirs \
  experiments/experiment_uniform/ \
  experiments/experiment_moderate/ \
  experiments/experiment_heterogeneous/ \
  --metric specialization_index
```

4. Statistical test:

```bash
python -m substrate test --experiment-dirs \
  experiments/experiment_uniform/ \
  experiments/experiment_heterogeneous/ \
  --test permutation --metric specialization_index
```

5. Expected outputs:

- `results/aggregate.csv` — All replicate-level specialization indices
- `results/comparison_plot.png` — Box plot of specialization index by condition
- `results/test_results.json` — Permutation test p-value and effect size

### Interpretation

If `specialization_index` is significantly higher (p < 0.01, Cohen's d > 0.5) in the heterogeneous condition compared to the uniform condition, and this holds in at least 8 of 10 replicates, the evidence supports the hypothesis that resource heterogeneity drives specialization.

If no significant difference is found, possible explanations include:
- Specialization requires additional mechanisms not present in current model
- Run duration insufficient for specialization to develop
- Agent cognitive capacity limits ability to specialize

These results should be reported as "not supported" and the null hypothesis cannot be rejected.
