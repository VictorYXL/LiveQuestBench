"""Veloren fixture admission, public bindings and private native endpoint scoring."""

from collections.abc import Callable
import inspect
import json
from pathlib import Path

from agent_framework.utils.tools import Tool
from game.bindings import Controls, GameBinding, bind_controls, validate_tools
from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory
from game.veloren.evaluators.endpoints import validate_displacement, validate_health, validate_inventory
from game.veloren.evaluators.endpoints import evaluate_state, validate_state
from game.veloren.evaluators.deaths import evaluate_deaths
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
            tools = (st.EXPEDITION_TOOLS if evaluator == "expedition" else
                     st.COMBAT_TOOLS if fixture.get("encounters") else st.BASE_TOOLS)
        validate_tools(st.agent_tools(), tools)
        if "RespawnTool" not in tools:
            tools = (*tools, "RespawnTool")
    elif tools is not None:
        raise ValueError("Tool allowlists are only supported for structured_tool tasks")
    evaluators: dict[str, Callable[..., dict]] = {
        "displacement": evaluate_displacement, "inventory": evaluate_inventory, "health": evaluate_health,
        "state": evaluate_state,
    }
    validators: dict[str, Callable[..., object]] = {
        "displacement": validate_displacement, "inventory": validate_inventory, "health": validate_health,
        "state": validate_state,
    }
    if evaluator == "source_supplies":
        from game.veloren.evaluators.pickups import evaluate_supplies, validate_supplies
        evaluators[evaluator] = evaluate_supplies
        validators[evaluator] = validate_supplies
        declared = [{"item": row["item"], "amount": row["amount"]} for row in fixture.get("supplies", [])]
        if not fixture.get("pickup_evidence") or parameters.get("supplies") != declared:
            raise ValueError("Original supply scoring requires matching native fixture sources and evidence")
    elif evaluator == "encounter_supplies":
        from game.veloren.evaluators.encounter_supplies import (
            evaluate_encounter_supplies, validate_encounter_supplies,
        )
        evaluators[evaluator] = evaluate_encounter_supplies
        validators[evaluator] = validate_encounter_supplies
        declared = [{"item": row["item"], "amount": row["amount"]} for row in fixture.get("supplies", [])]
        if not fixture.get("pickup_evidence") or parameters.get("supplies") != declared:
            raise ValueError("Encounter supplies require matching native fixture sources and evidence")
    elif evaluator in ("encounter", "damage"):
        from game.veloren.evaluators.encounter import evaluate_damage, evaluate_encounter, validate_encounter
        evaluators.update(encounter=evaluate_encounter, damage=evaluate_damage)
        validators.update(encounter=validate_encounter, damage=validate_encounter)
    elif evaluator == "expedition":
        from game.veloren.evaluators.expedition import evaluate_expedition, validate_expedition
        evaluators[evaluator] = evaluate_expedition
        validators[evaluator] = validate_expedition
    elif evaluator == "contract":
        from game.veloren.evaluators.contract import evaluate_contract, validate_contract
        evaluators[evaluator] = evaluate_contract
        validators[evaluator] = validate_contract
    elif evaluator == "glide_route":
        from game.veloren.evaluators.glide_route import evaluate_glide_route, validate_glide_route
        evaluators[evaluator] = evaluate_glide_route
        validators[evaluator] = validate_glide_route
    elif evaluator == "route_transfer":
        from game.route_transfer import build_layout
        from game.veloren.evaluators.route_transfer import evaluate_route, validate_route
        from game.veloren.fixture import solid_voxels
        evaluators[evaluator] = evaluate_route
        validators[evaluator] = validate_route
        expected = build_layout(parameters["variant"], tuple(parameters["origin"]), headroom=3)["solid"]
        expected |= solid_voxels({**fixture, "blocks": []})
        if not fixture.get("route_evidence") or solid_voxels(fixture) != expected:
            raise ValueError("Route-transfer fixture must match the scored layout and enable native evidence")
    elif evaluator == "itinerary":
        from game.veloren.evaluators.itinerary import evaluate_itinerary, validate_itinerary
        evaluators[evaluator] = evaluate_itinerary
        validators[evaluator] = validate_itinerary
        if not fixture.get("route_evidence"):
            raise ValueError("Itinerary scoring requires native route evidence")
    elif evaluator == "active_build":
        from game.veloren.evaluators.active_build import evaluate_active_build, validate_active_build
        evaluators[evaluator] = evaluate_active_build
        validators[evaluator] = validate_active_build
    elif evaluator == "harvest":
        from game.veloren.evaluators.harvest import evaluate_harvest, validate_harvest
        evaluators[evaluator] = evaluate_harvest
        validators[evaluator] = validate_harvest
        if not fixture.get("harvest_sites") or not {
            tuple(point) for point in parameters["source_cells"]
        } <= {tuple(point) for point in fixture["harvest_sites"]}:
            raise ValueError("Scored harvest sources must be declared native mushroom cells")
    elif evaluator == "message":
        from game.veloren.evaluators.message import evaluate_message, validate_message
        evaluators[evaluator] = evaluate_message
        validators[evaluator] = validate_message
        if "message_contract" not in fixture:
            raise ValueError("Message scoring requires unprotected native Message preparation")
    elif evaluator == "market":
        from game.veloren.evaluators.market import evaluate_market, validate_market
        evaluators[evaluator] = evaluate_market
        validators[evaluator] = validate_market
        if ("market" not in fixture or parameters.get("bundles") != fixture["market"]["bundles"]
                or parameters.get("coin_reserve") != fixture["market"]["coin_reserve"]):
            raise ValueError("Scored market bundles and reserve must match native preparation")
    if evaluator not in evaluators:
        raise ValueError(f"Unknown Veloren evaluator: {evaluator}")
    score = evaluators[evaluator]
    inspect.signature(score).bind(Path(), Path(), **parameters)
    validators[evaluator](**parameters)
    if evaluator in ("encounter", "encounter_supplies", "expedition", "damage", "active_build") and set(parameters["roles"]) != {
        row["role"] for row in game.fixture.get("encounters", [])
    }:
        raise ValueError("Scored encounter roles must match the fixture's designated targets")
    if parameters.get("motion") is not None and not (
        fixture.get("motion_evidence") or fixture.get("glide_evidence")
    ):
        raise ValueError("Motion scoring requires private fixture motion evidence")
    if parameters.get("glide_landing") is not None and not fixture.get("glide_evidence"):
        raise ValueError("Glide landing scoring requires private fixture glide evidence")
    if evaluator == "glide_route" and not fixture.get("glide_evidence"):
        raise ValueError("Ordered gliding requires private fixture glide evidence")
    if parameters.get("marker_arrival") is not None and "native_site" not in fixture:
        raise ValueError("Dialogue marker arrival requires an admitted native settlement fixture")
    if (parameters.get("sword_skills") is not None or parameters.get("auxiliary_ability") is not None
            ) and "sword_skill_points" not in fixture:
        raise ValueError("Skill scoring requires declared native Sword points")
    if parameters.get("companion") is not None and "companion" not in fixture:
        raise ValueError("Companion scoring requires a declared native owned companion")
    if evaluator == "contract" and "contract" not in fixture:
        raise ValueError("Contract scoring requires a declared native Slay fixture")

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
        if parameters.get("marker_arrival") is not None and json.loads(
            (before / "observation.json").read_text()
        )["dialogue_markers"]:
            raise RuntimeError("Dialogue marker task must start without received directions")

    return GameBinding(game, controls, evaluate, verify_initial, metrics=evaluate_deaths)
