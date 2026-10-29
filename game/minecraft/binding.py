"""Minecraft fixture admission, public bindings and native private scoring."""

from collections.abc import Callable
import inspect
from pathlib import Path

from agent_framework.utils.tools import Tool
from game.bindings import Controls, GameBinding, bind_controls, validate_tools
from game.minecraft.evaluators.deaths import evaluate_deaths
from game.minecraft.evaluators.inventory import evaluate_inventory, inventory, validate_requirements
from game.minecraft.evaluators.state import action_events, evaluate_state, validate_state
from game.minecraft.evaluators.cargo import evaluate_cargo, validate_cargo, verify_initial_cargo
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
    expedition = None
    if evaluator == "expedition":
        from game.minecraft.evaluators.expedition import evaluate_expedition, registry, verify_initial as verify_expedition
        expedition = registry(world_path)
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
            else:
                tools = st.TRADING_TOOLS
        validate_tools(st.agent_tools(), tools)
        if "RespawnTool" not in tools:
            tools = (*tools, "RespawnTool")
    elif tools is not None:
        raise ValueError("Tool allowlists are only supported for structured_tool tasks")
    if evaluator == "inventory":
        inspect.signature(evaluate_inventory).bind(Path(), Path(), None, **parameters)
        validate_requirements(parameters["requirements"])
        score: Callable[..., dict] = evaluate_inventory
    elif evaluator == "air_salvage":
        from game.minecraft.evaluators.air_salvage import evaluate_air_salvage, verify_initial_air_salvage
        inspect.signature(evaluate_air_salvage).bind(Path(), Path(), None, **parameters)
        validate_cargo(**parameters)
        score = evaluate_air_salvage
    elif evaluator == "state":
        inspect.signature(evaluate_state).bind(Path(), Path(), None, **parameters)
        validate_state(**parameters)
        score = evaluate_state
    elif evaluator == "shielded_cargo":
        from game.minecraft.evaluators.shielded_cargo import (
            evaluate_shielded_cargo, verify_initial_shielded_cargo,
        )
        validate_cargo(**parameters)
        score = evaluate_shielded_cargo
    elif evaluator == "structure":
        from game.minecraft.evaluators.structure import evaluate_structure, validate_config
        inspect.signature(evaluate_structure).bind(Path(), Path(), **parameters)
        validate_config(parameters["config"])
        score = evaluate_structure
    elif evaluator == "firebreak":
        from game.minecraft.evaluators.firebreak import evaluate_firebreak, verify_initial_firebreak
        inspect.signature(evaluate_firebreak).bind(Path(), Path(), None, **parameters)
        validate_state(**parameters)
        score = evaluate_firebreak
    elif evaluator == "expedition":
        inspect.signature(evaluate_expedition).bind(Path(), Path(), None, **parameters)
        score = evaluate_expedition
    elif evaluator == "dispatch":
        from game.minecraft.evaluators.dispatch import evaluate_dispatch, furnace_evidence
        validate_state(**parameters)
        furnace_evidence(world_path)
        score = evaluate_dispatch
    elif evaluator == "cargo":
        inspect.signature(evaluate_cargo).bind(Path(), Path(), None, **parameters)
        validate_cargo(**parameters)
        score = evaluate_cargo
    elif evaluator == "extraction":
        from game.minecraft.evaluators.extraction import evaluate_extraction, validate_extraction
        validate_extraction(**parameters)
        score = evaluate_extraction
    elif evaluator == "switch_transfer":
        from game.minecraft.evaluators.switch_transfer import evaluate_switch, verify_initial_switch
        validate_state(**parameters)
        score = evaluate_switch
    elif evaluator == "route_transfer":
        from game.minecraft.evaluators.route_transfer import evaluate_route, validate_route, verify_layout
        validate_route(**parameters)
        verify_layout(world_path, **parameters)
        score = evaluate_route
    elif evaluator == "market":
        from game.minecraft.evaluators.market import evaluate_market, validate_market
        validate_market(**parameters)
        score = evaluate_market
    elif evaluator == "workshop":
        from game.minecraft.evaluators.workshop import evaluate_workshop, order_events
        validate_state(**parameters)
        score = evaluate_workshop
    elif evaluator == "raid":
        from game.minecraft.evaluators.raid import evaluate_raid, verify_initial_raid
        validate_state(**parameters)
        if not any(row["id"] == "minecraft:bad_omen" for row in state.effects):
            raise ValueError("Prepared village defense requires a declared native Bad Omen opening")
        score = evaluate_raid
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
        if evaluator == "shielded_cargo":
            verify_initial_shielded_cargo(before, game.player_uuid, **parameters)
        if evaluator == "expedition":
            verify_expedition(before, game.player_uuid)
        if evaluator == "cargo":
            verify_initial_cargo(before, game.player_uuid, **parameters)
        if evaluator == "switch_transfer":
            verify_initial_switch(before, game.player_uuid, **parameters)
        if evaluator == "route_transfer":
            verify_layout(before, **parameters)
        if evaluator == "workshop" and order_events(before):
            raise RuntimeError("Workshop milestone history was not empty before measured play")
        if evaluator == "dispatch" and furnace_evidence(before)["events"]:
            raise RuntimeError("Furnace production history must start empty")
        if evaluator == "raid":
            verify_initial_raid(before, game.player_uuid)
        if evaluator == "air_salvage":
            verify_initial_air_salvage(before, game.player_uuid, **parameters)
        if evaluator == "state" and parameters.get("action_sequence") is not None and action_events(before):
            raise RuntimeError("Native action evidence was not empty before measured play")
        if evaluator == "firebreak":
            verify_initial_firebreak(before, game.player_uuid, **parameters)

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

    def metrics(before: Path, after: Path) -> dict:
        assert game.player_uuid is not None
        return evaluate_deaths(before, after, game.player_uuid)

    return GameBinding(game, controls, evaluate, verify_initial, metrics=metrics)
