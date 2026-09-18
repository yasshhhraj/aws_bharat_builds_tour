"""Small common interface for deterministic Checkpoint 1 agents."""

from abc import ABC, abstractmethod

from packages.domain.enums import AgentName
from packages.domain.models import TrajectoryState
from packages.governor import ObserverGovernor


class BaseAgent(ABC):
    name: AgentName

    @abstractmethod
    def run(self, state: TrajectoryState, governor: ObserverGovernor) -> str:
        """Perform this role's bounded work and return a human-readable summary."""
