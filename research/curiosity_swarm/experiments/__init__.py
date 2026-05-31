"""Example investigations that ship with the curiosity swarm.

Each module demonstrates a long-horizon scientific investigation using
the Substrate tick runtime. They serve as templates for new investigations.

Available investigations:
  - hubble_tension: Resolve the Hubble constant tension
  - dark_matter: Investigate dark matter distribution patterns
  - protein_folding: Study protein folding dynamics
  - social_networks: Analyze emergent social network structures
  - economic_complexity: Study trade network specialization
"""

from research.curiosity_swarm.experiments.hubble_tension import HubbleTensionInvestigation
from research.curiosity_swarm.experiments.dark_matter import DarkMatterInvestigation
from research.curiosity_swarm.experiments.protein_folding import ProteinFoldingInvestigation

__all__ = [
    "HubbleTensionInvestigation",
    "DarkMatterInvestigation",
    "ProteinFoldingInvestigation",
]
