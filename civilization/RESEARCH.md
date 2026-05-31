# Civilization Simulation: Mechanism Design Document

## Memory

### Why Episodic and Semantic?
- **Episodic memory** stores raw timestamped experiences (who did what, when). This is the agent's direct experience stream. It enables temporal reasoning: "what happened the last time I traded with agent X?"
- **Semantic memory** stores extracted facts and knowledge (concept-relation-target triples). It enables generalization: "agent X is trustworthy" is a fact derived from many episodic experiences of trading with X.

### Memory Aging and Forgetting
- Episodic memories decay with time. Old, unused memories are automatically forgotten (removed after a configurable threshold). This prevents infinite memory growth and models biological forgetting.
- Semantic facts have confidence scores. Conflicting facts from different sources resolve by keeping the higher-confidence version. Facts are not deleted — they accumulate and compete by confidence.

### Inheritance
- Semantic memory supports inheritance: child agents inherit parent facts at birth. This models cultural transmission of knowledge across generations without requiring each agent to re-discover everything.

### Measurement Targets
- Episodic recall accuracy (does query return relevant episodes?)
- Forget rate vs. memory capacity
- Semantic query coverage (how many facts exist per agent?)
- Inheritance fidelity (do children retain parent knowledge?)

---

## Economy

### Scarcity
- Energy is the universal currency. Every action costs energy. Agents must harvest resources to replenish energy. This creates a hard budget constraint — no agent can act indefinitely without resource access.
- Resources are finite, located at positions, and regenerate slowly. This forces competition and spatial coordination.

### Trade as Coordination
- Trade allows agents to exchange resources/energy voluntarily. Trade is a positive-sum interaction — both parties gain access to things they lack.
- Trade proposals specify exact offers and requests. Agents can accept or reject. This creates a natural price-discovery mechanism.
- Trade telemetry tracks volume, partner networks, and success rates.

### Measurement Targets
- Energy distribution (Gini coefficient across agents)
- Trade volume per agent per tick
- Trade success rate
- Resource depletion rates
- Price convergence (ratio of offer to request over time)

---

## Social

### Communication Patterns
- Direct messaging enables one-to-one communication with priority levels (LOW to CRITICAL).
- Broadcast enables one-to-many communication (public announcements).
- Messages are stored in inboxes; agents poll their inbox to receive.
- Communication telemetry tracks who talks to whom, forming a communication network graph.

### Reputation as Feedback
- Reputation is a global score adjusted by agent actions (trade completion, alliance behavior, etc.).
- Pairwise ratings let agents directly score each other (-1.0 to 1.0), which feeds into global reputation.
- Reputation affects trade willingness — agents with low reputation may struggle to find trade partners.
- Reputation is a decentralized feedback mechanism. No central authority judges agents.

### Alliances
- Voluntary, dissolved when membership drops below 2.
- Alliance formation signals trust and cooperation.
- Alliance duration and member counts track stability.

### Measurement Targets
- Communication network density and centrality
- Reputation distribution (is it meritocratic?)
- Alliance formation/dissolution rates
- Correlation between reputation and trade volume
- Reciprocity in communication patterns

---

## Evolution

### Mutation for Diversity
- Traits (energy_efficiency, harvest_rate, social_aptitude, memory_capacity) mutate during reproduction with small random Gaussian deltas.
- Mutation rate is configurable per agent (can itself evolve over time via trait inheritance).
- Mutation prevents population convergence to a single optimum and enables adaptation to changing environments.

### Lineage for Tracking
- Every birth registers parent-child relationships with generation counting.
- Ancestor/descendant queries enable phylogenetic analysis.
- Lineage survival rates measure which genetic lines thrive.
- Generation tracking enables measuring evolutionary speed.

### Asexual and Sexual Reproduction
- Agents can reproduce alone (asexual, cloning with mutation) or with a partner (sexual, blending traits).
- Reproduction has energy costs, preventing unbounded population growth.

### Measurement Targets
- Trait distribution over generations (mean, variance)
- Mutation impact on trait values
- Lineage survival rate by generation
- Population genetic diversity (effective population size)
- Correlation between traits and reproductive success

---

## Tools

### Innovation Diffusion
- Agents create tools with specific effects. Tools are cultural artifacts, not physical objects.
- Tool creation requires an agent to have sufficient energy/knowledge.
- Tools spread through adoption (agents choose to use a tool) and sharing (one agent teaches another).

### Cultural Evolution
- Tools are adopted and can be abandoned. This models cultural evolution — ideas compete for mindshare.
- Adoption rate measures how quickly a tool spreads through the population.
- Tools accumulate adoption counts — popular tools become more visible.

### Measurement Targets
- Tool creation rate per agent
- Tool adoption curve (S-curve? Exponential?)
- Tool abandonment rate
- Correlation between tool adoption and agent success (energy, reproduction)
- Tool diversity (are agents converging on the same tools or diversifying?)

---

## What Counts as Evidence

- **Emergent hierarchy**: If over time certain agents systematically accumulate more energy, form larger alliance networks, have more offspring, or their tools spread farther — that is evidence of emergent hierarchy without any agent being designated as a leader.
- **Division of labor**: If agents specialize (some focus on resource harvesting, others on tool creation, others on trade) this appears in telemetry as asymmetric resource/trade profiles.
- **Cooperation**: Repeated trade between the same agent pairs, alliance longevity, and positive reputation scores indicate cooperation.
- **Cultural evolution**: Tool diffusion patterns, modification of tools by adopters, and lineage of tool variants indicate cultural evolution.
- **Adaptation**: Trait shifts across generations in response to resource scarcity or social density indicate evolutionary adaptation.

All telemetry is emitted via the core event bus and can be consumed by external analysis tools in real time.
