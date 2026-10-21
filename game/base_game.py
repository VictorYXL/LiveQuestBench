from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar


InterfaceT = TypeVar("InterfaceT")


class BaseGame(ABC, Generic[InterfaceT]):
    """Operations for one game session; the benchmark owns Episode orchestration.

    Concrete constructors accept game-specific configuration and fixture settings.
    InterfaceT is the restricted VM or ST interface, not this administrative object.
    """

    @abstractmethod
    async def start(self) -> None:
        """Initialize and validate a fresh session without starting measured play."""
        raise NotImplementedError

    @abstractmethod
    async def begin(self) -> None:
        """Enable play after the runner has collected initial evidence."""
        raise NotImplementedError

    @abstractmethod
    async def end(self) -> None:
        """Disable further Agent actions and establish the final evidence boundary."""
        raise NotImplementedError

    @abstractmethod
    def get_agent_interface(self) -> InterfaceT:
        """Return allowed observation/action access without reset or scorer access."""
        raise NotImplementedError

    @abstractmethod
    async def save_snapshot(self, destination: Path) -> Path:
        """Save private evidence and return its path; raise on acquisition failure.

        The runner chooses when to call this operation. The game must document
        capture timing and consistency; this method alone guarantees no cutoff.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release owned resources, including after partial startup; allow repeats."""
        raise NotImplementedError
