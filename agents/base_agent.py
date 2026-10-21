from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar


InterfaceT = TypeVar("InterfaceT")


class StopReason(StrEnum):
    """Why the benchmark requests retirement, independently of task success."""

    DEADLINE = "deadline"
    GAME_TERMINAL = "game_terminal"
    OPERATOR_CANCEL = "operator_cancel"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


class AgentExitReason(StrEnum):
    """Native run outcomes; execution errors must propagate as exceptions."""

    COMPLETED = "completed"
    GAVE_UP = "gave_up"
    RETURNED = "returned"
    NATIVE_LIMIT = "native_limit"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AgentExit:
    """An Agent's reported exit, never a score or proof of task completion.

    STOPPED requires a benchmark stop request. Wrappers preserve native limits
    and reasons instead of treating all normal upstream returns as completion.
    """

    reason: AgentExitReason
    message: str = ""
    native_reason: str | None = None


@dataclass(frozen=True)
class AgentContext(Generic[InterfaceT]):
    """Public inputs for one measured attempt, not an administrative game handle.

    Times use the benchmark host's monotonic clock in nanoseconds. A remote
    adapter must translate them to a duration hint, not compare host timestamps
    with a remote clock. The runner/game gate enforces the actual deadline.
    Frozen fields do not make the interface immutable or isolate untrusted code.
    """

    episode_id: str
    task: str
    interface: InterfaceT
    started_at_ns: int
    deadline_at_ns: int
    game_instructions: str = ""

    def __post_init__(self) -> None:
        if not self.episode_id.strip():
            raise ValueError("episode_id must not be blank")
        if not self.task.strip():
            raise ValueError("task must not be blank")
        if self.started_at_ns < 0 or self.deadline_at_ns <= self.started_at_ns:
            raise ValueError("deadline_at_ns must be greater than nonnegative started_at_ns")


class BaseAgent(ABC, Generic[InterfaceT]):
    """Benchmark-facing contract implemented by a native Agent or its Wrapper.

    Use a fresh instance per attempt. Constructors accept implementation-specific
    Agent/model configuration; this base imposes no client or transport.
    Wrappers may delegate to an existing upstream controller or process.
    """

    @abstractmethod
    async def run(self, context: AgentContext[InterfaceT]) -> AgentExit:
        """Own one complete run using only approved public inputs and interfaces.

        Preserve upstream observation scheduling and tool execution. Return an
        explicit AgentExit; propagate errors and cancellation rather than
        converting them to completion. The evaluator determines task success.
        """
        raise NotImplementedError

    @abstractmethod
    async def stop(self, reason: StopReason) -> None:
        """Request retirement; allow repeated calls during or after run.

        Returning acknowledges the request, not guaranteed worker termination.
        The runner revokes game access before waiting for cooperative shutdown.
        Do not destroy game-owned connections needed for final evidence.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release owned resources after run/stop, including partial startup.

        Allow repeats. Preserve game-owned resources and propagate cleanup
        errors. This base does not implement process supervision or deadlines.
        """
        raise NotImplementedError
