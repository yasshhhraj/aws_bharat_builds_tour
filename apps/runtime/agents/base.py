"""Small common interface for deterministic governed agents."""

from abc import ABC, abstractmethod

from packages.domain.enums import AgentName
from packages.domain.models import TrajectoryState
from packages.governor import ManifestGovernor


class BaseAgent(ABC):
    name: AgentName

    @abstractmethod
    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        """Perform this role's bounded work and return a human-readable summary."""
