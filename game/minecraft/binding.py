"""Minecraft fixture admission, public bindings and native private scoring."""

from collections.abc import Callable
import asyncio
from functools import partial
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
from game.minecraft import structured_tools as st
from game.backends.x11 import interface as vm


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
    instance_selection = None
    if evaluator == "function_replication":
        from game.minecraft.evaluators.function_replication import select_world
        world_path, instance_selection = select_world(world_path)
    if evaluator == "camel_delivery_flush_v4":
        from game.minecraft.fixtures.camel_delivery_registration import select_world
        world_path, instance_selection = select_world(world_path)
    validate_world(world_path)
    expedition = None
    if evaluator == "expedition":
        from game.minecraft.evaluators.expedition import evaluate_expedition, registry, verify_initial as verify_expedition
        expedition = registry(world_path)
    instance, difficulty = fixture["instance"], fixture["difficulty"]
    if instance != "1.20.4" or difficulty not in ("peaceful", "easy", "normal", "hard"):
        raise ValueError("Unsupported Minecraft instance or difficulty")
    assert isinstance(instance, str) and isinstance(difficulty, str)
    server_factory = None
    evaluation_loop = None
    if evaluator == "function_replication":
        from game.minecraft.runtime.observed_server import ObservedServer
        server_factory = ObservedServer
    if evaluator == "camel_delivery_flush_v4":
        from game.minecraft.fixtures.camel_delivery_start import CourierInitializationServer
        server_factory = partial(CourierInitializationServer, template=world_path)
    game = MinecraftGame(
        output_dir=output_dir, track=task_type, world_path=world_path,
        instance=instance, difficulty=difficulty, player_state=state,
        headless=headless, recording=recording, recording_fps=recording_fps, recording_path=recording_path,
        server_factory=server_factory,
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
    if evaluator == "function_replication":
        from game.minecraft.evaluators.function_replication import initial_function, evaluate_function
        if parameters:
            raise ValueError("Hidden circuit selection is native fixture state, not public parameters")
        initial_function(world_path)
        score = evaluate_function
    elif evaluator == "camel_delivery_flush_v4":
        from game.minecraft.fixtures.camel_delivery_flush_v4 import evaluate as evaluate_courier
        from game.minecraft.fixtures.camel_delivery_registration import verify_initial as verify_courier, SPEEDS
        if parameters:
            raise ValueError("Native courier response selection is private fixture state, not public parameters")
        score = evaluate_courier
    elif evaluator == "target_lock":
        from game.minecraft.evaluators.target_lock import evaluate_lock
        if parameters:
            raise ValueError("The hidden acceptance window is native fixture state, not public parameters")
        if not (world_path / "livequest-lock-public.json").is_file():
            raise ValueError("Missing native lock fixture")
        score = evaluate_lock
    elif evaluator == "timed_routing":
        from game.minecraft.evaluators.timed_routing import evaluate_routing, verify_initial as verify_routing
        if parameters:
            raise ValueError("Timed routing has no public hidden-state parameters")
        verify_routing(world_path)
        score = evaluate_routing
    elif evaluator == "circuit_feedback":
        from game.minecraft.evaluators.circuit_feedback import evaluate_feedback, evidence, verify_initial as verify_feedback
        validate_state(**parameters)
        evidence(world_path)
        score = evaluate_feedback
    elif evaluator == "inventory":
        inspect.signature(evaluate_inventory).bind(Path(), Path(), None, **parameters)
        validate_requirements(parameters["requirements"])
        score: Callable[..., dict] = evaluate_inventory
    elif evaluator == "air_salvage":
        from game.minecraft.evaluators.air_salvage import evaluate_air_salvage, verify_initial_air_salvage
        inspect.signature(evaluate_air_salvage).bind(Path(), Path(), None, **parameters)
        validate_cargo(**parameters)
        score = evaluate_air_salvage
    elif evaluator == "farm":
        from game.minecraft.evaluators.farm import evaluate_farm, farm_evidence
        validate_state(**parameters)
        farm_evidence(world_path)
        score = evaluate_farm
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
    elif evaluator == "shelter":
        from game.minecraft.evaluators.shelter import evaluate_shelter
        inspect.signature(evaluate_shelter).bind(Path(), Path(), None, **parameters)
        validate_state(**parameters)
        score = evaluate_shelter
    elif evaluator == "irrigation":
        from game.minecraft.evaluators.irrigation import evaluate_irrigation, stable_ticks
        validate_state(**parameters)
        stable_ticks(world_path)
        score = evaluate_irrigation
    elif evaluator == "gallery":
        from game.minecraft.evaluators.gallery import evaluate_gallery, gallery_evidence
        validate_state(**parameters)
        gallery_evidence(world_path)
        score = evaluate_gallery
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
    elif evaluator == "shaft":
        from game.minecraft.evaluators.shaft import evaluate_shaft, validate_shaft, visits as shaft_visits
        validate_shaft(**parameters)
        shaft_visits(world_path)
        score = evaluate_shaft
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
    elif evaluator == "quarry":
        from game.minecraft.evaluators.quarry import evaluate_quarry
        inspect.signature(evaluate_quarry).bind(Path(), Path(), None, **parameters)
        validate_cargo(**parameters)
        score = evaluate_quarry
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
    elif evaluator == "replica":
        from game.minecraft.evaluators.replica import evaluate_replica, validate_replica, verify_initial_replica
        validate_replica(**parameters)
        score = evaluate_replica
    elif evaluator == "raid":
        from game.minecraft.evaluators.raid import evaluate_raid, verify_initial_raid
        validate_state(**parameters)
        if not any(row["id"] == "minecraft:bad_omen" for row in state.effects):
            raise ValueError("Prepared village defense requires a declared native Bad Omen opening")
        score = evaluate_raid
    else:
        raise ValueError(f"Unknown Minecraft evaluator: {evaluator}")

    def verify_initial(before: Path) -> None:
        nonlocal evaluation_loop
        assert game.player_uuid is not None
        expected: dict[str, int] = {}
        for item in state.inventory:
            name = item["item"] if ":" in item["item"] else "minecraft:" + item["item"]
            expected[name] = expected.get(name, 0) + item["count"]
        if inventory(before, game.player_uuid) != expected:
            raise RuntimeError("Initial native inventory differs from task initialization")
        if evaluator == "circuit_feedback":
            verify_feedback(before, game.player_uuid)
        if evaluator == "function_replication":
            initial_function(before)
            evaluation_loop = asyncio.get_running_loop()
            import json
            (game.output_dir / "native-function-instance.json").write_text(
                json.dumps(instance_selection, indent=2) + "\n")
        if evaluator == "timed_routing":
            verify_routing(before)
        if evaluator == "camel_delivery_flush_v4":
            assert instance_selection is not None
            if verify_courier(before, game.player_uuid) != SPEEDS[instance_selection["instance_index"]]:
                raise RuntimeError("Initial native courier response differs from the selected instance")
            import json
            (game.output_dir / "native-camel-instance.json").write_text(
                json.dumps(instance_selection, indent=2) + "\n")
        if evaluator == "shielded_cargo":
            verify_initial_shielded_cargo(before, game.player_uuid, **parameters)
        if evaluator == "expedition":
            verify_expedition(before, game.player_uuid)
        if evaluator in ("cargo", "quarry"):
            verify_initial_cargo(before, game.player_uuid, **parameters)
        if evaluator == "switch_transfer":
            verify_initial_switch(before, game.player_uuid, **parameters)
        if evaluator == "route_transfer":
            verify_layout(before, **parameters)
        if evaluator == "replica":
            verify_initial_replica(before, **parameters)
        if evaluator == "workshop" and order_events(before):
            raise RuntimeError("Workshop milestone history was not empty before measured play")
        if evaluator == "dispatch" and furnace_evidence(before)["events"]:
            raise RuntimeError("Furnace production history must start empty")
        if evaluator == "raid":
            verify_initial_raid(before, game.player_uuid)
        if evaluator == "farm" and farm_evidence(before)["events"]:
            raise RuntimeError("Farm breeding history must start empty")
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
        if evaluator == "function_replication":
            assert game.player_uuid is not None
            return score(before, after, game.player_uuid, game=game, loop=evaluation_loop)
        if evaluator == "structure":
            return score(before, after, **parameters)
        assert game.player_uuid is not None
        return score(before, after, game.player_uuid, **parameters)

    def metrics(before: Path, after: Path) -> dict:
        assert game.player_uuid is not None
        return evaluate_deaths(before, after, game.player_uuid)

    return GameBinding(game, controls, evaluate, verify_initial, metrics=metrics)
