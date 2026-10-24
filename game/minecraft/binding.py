"""Minecraft fixture admission, public bindings and native private scoring."""

from collections.abc import Callable
import inspect
from pathlib import Path

from agent_framework.utils.tools import Tool
from game.bindings import Controls, GameBinding, bind_controls, validate_tools
from game.minecraft.evaluators.inventory import evaluate_inventory, inventory, validate_requirements
from game.minecraft.evaluators.structure import evaluate_structure, validate_config
from game.minecraft.evaluators.expedition import evaluate_expedition, registry, verify_initial as verify_expedition
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.runtime.session import validate_world
from game.minecraft.structured_tools import interface as st
from game.minecraft.visual_motor import interface as vm


def create_binding(
    *, fixture: dict[str, object], task_type: str, evaluator: str, parameters: dict[str, object],
    tools: tuple[str, ...] | None, output_dir: Path, headless: bool, recording: bool, recording_fps: int,
    recording_path: Path | None = None,
) -> GameBinding:
    required = {"world_path", "instance", "difficulty", "player_state"}
    if set(fixture) != required:
        raise ValueError(f"Minecraft fixture requires exactly {sorted(required)}")
    values = fixture["player_state"]
    if not isinstance(values, dict):
        raise ValueError("player_state must be a mapping")
    state = PlayerState.from_dict(values)
    path = fixture["world_path"]
    if not isinstance(path, str) or not path.strip():
        raise ValueError("world_path must be nonempty text")
    world_path = Path(path)
    validate_world(world_path)
    expedition = registry(world_path) if evaluator == "expedition" else None
    instance, difficulty = fixture["instance"], fixture["difficulty"]
    if instance != "1.20.4" or difficulty not in ("peaceful", "easy", "normal", "hard"):
        raise ValueError("Unsupported Minecraft instance or difficulty")
    assert isinstance(instance, str) and isinstance(difficulty, str)
    game = MinecraftGame(
        output_dir=output_dir, track=task_type, world_path=world_path,
        instance=instance, difficulty=difficulty, player_state=state,
        headless=headless, recording=recording, recording_fps=recording_fps, recording_path=recording_path,
    )
    if task_type == "structured_tool":
        if tools is None:
            if expedition is None:
                tools = st.BASE_TOOLS
            elif "merchants" not in expedition:
                tools = st.EXPEDITION_TOOLS
        validate_tools(st.agent_tools(), tools)
    elif tools is not None:
        raise ValueError("Tool allowlists are only supported for structured_tool tasks")
    if evaluator == "inventory":
        inspect.signature(evaluate_inventory).bind(Path(), Path(), None, **parameters)
        validate_requirements(parameters["requirements"])
        score: Callable[..., dict] = evaluate_inventory
    elif evaluator == "structure":
        inspect.signature(evaluate_structure).bind(Path(), Path(), **parameters)
        validate_config(parameters["config"])
        score = evaluate_structure
    elif evaluator == "expedition":
        inspect.signature(evaluate_expedition).bind(Path(), Path(), None, **parameters)
        score = evaluate_expedition
    else:
        raise ValueError(f"Unknown Minecraft evaluator: {evaluator}")

    def verify_initial(before: Path) -> None:
        assert game.player_uuid is not None
        expected: dict[str, int] = {}
        for item in state.inventory:
            name = item["item"] if ":" in item["item"] else "minecraft:" + item["item"]
            expected[name] = expected.get(name, 0) + item["count"]
        if inventory(before, game.player_uuid) != expected:
            raise RuntimeError("Initial native inventory differs from task initialization")
        if evaluator == "expedition":
            verify_expedition(before, game.player_uuid)

    def controls() -> tuple[Controls, list[Tool[Controls]]]:
        public = game.get_agent_interface()
        if isinstance(public, vm.MotorInterface):
            return bind_controls(public, vm.agent_observation, vm.agent_tools(), None)
        return bind_controls(public, st.agent_observation, st.agent_tools(), tools)

    def evaluate(before: Path, after: Path) -> dict:
        if evaluator == "structure":
            return score(before, after, **parameters)
        assert game.player_uuid is not None
        return score(before, after, game.player_uuid, **parameters)

    return GameBinding(game, controls, evaluate, verify_initial)
