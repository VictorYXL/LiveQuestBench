"""Veloren fixture admission, public bindings and private native endpoint scoring."""

from collections.abc import Callable
import inspect
from pathlib import Path

from agent_framework.utils.tools import Tool
from game.bindings import Controls, GameBinding, bind_controls, validate_tools
from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory
from game.veloren.evaluators.endpoints import validate_displacement, validate_health, validate_inventory
from game.veloren.evaluators.endpoints import evaluate_state, validate_state
from game.veloren.evaluators.encounter import evaluate_encounter, validate_encounter
from game.veloren.evaluators.expedition import evaluate_expedition, validate_expedition
from game.veloren.game import VelorenGame
from game.veloren.structured_tools import interface as st
from game.veloren.visual_motor import interface as vm


def create_binding(
    *, fixture: dict[str, object], task_type: str, evaluator: str, parameters: dict[str, object],
    tools: tuple[str, ...] | None, output_dir: Path, headless: bool, recording: bool, recording_fps: int,
    recording_path: Path | None = None,
) -> GameBinding:
    game = VelorenGame(
        output_dir=output_dir, track=task_type, fixture=fixture,
        headless=headless, recording=recording, recording_fps=recording_fps, recording_path=recording_path,
    )
    if task_type == "structured_tool":
        if tools is None:
            tools = tuple(st.SPECS) if fixture.get("encounters") else st.BASE_TOOLS
        validate_tools(st.agent_tools(), tools)
    elif tools is not None:
        raise ValueError("Tool allowlists are only supported for structured_tool tasks")
    evaluators: dict[str, Callable[..., dict]] = {
        "displacement": evaluate_displacement, "inventory": evaluate_inventory, "health": evaluate_health,
        "state": evaluate_state, "encounter": evaluate_encounter, "expedition": evaluate_expedition,
    }
    validators: dict[str, Callable[..., object]] = {
        "displacement": validate_displacement, "inventory": validate_inventory, "health": validate_health,
        "state": validate_state, "encounter": validate_encounter, "expedition": validate_expedition,
    }
    if evaluator not in evaluators:
        raise ValueError(f"Unknown Veloren evaluator: {evaluator}")
    score = evaluators[evaluator]
    inspect.signature(score).bind(Path(), Path(), **parameters)
    validators[evaluator](**parameters)
    if evaluator in ("encounter", "expedition") and set(parameters["roles"]) != {
        row["role"] for row in game.fixture.get("encounters", [])
    }:
        raise ValueError("Scored encounter roles must match the fixture's designated targets")

    def controls() -> tuple[Controls, list[Tool[Controls]]]:
        public = game.get_agent_interface()
        if isinstance(public, vm.MotorInterface):
            return bind_controls(public, vm.agent_observation, vm.agent_tools(), None)
        return bind_controls(public, st.agent_observation, st.agent_tools(), tools)

    def evaluate(before: Path, after: Path) -> dict:
        return score(before, after, **parameters)

    def verify_initial(before: Path) -> None:
        if not (before / "observation.json").is_file():
            raise RuntimeError("Missing initial Veloren observation")

    return GameBinding(game, controls, evaluate, verify_initial)
