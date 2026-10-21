from abc import ABC, abstractmethod
from typing import Generic, TypeVar


InterfaceT = TypeVar("InterfaceT")


class BaseAgent(ABC, Generic[InterfaceT]):
    """One fresh Agent instance per Episode, with an autonomous decision loop."""

    @abstractmethod
    async def run(self, task: str, interface: InterfaceT) -> None:
        """Run until completion or stop, using only public task text and interfaces.

        Returning is not proof of task success; the evaluator owns that decision.
        Propagate execution errors rather than turning them into normal completion.
        """
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """End ongoing work and release Agent-owned resources; allow repeats.

        The runner may call this while run() is active or after it has failed.
        It must not destroy game-owned connections needed for final evidence.
        """
        raise NotImplementedError
