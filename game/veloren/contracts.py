"""Private preparation and native lifecycle joins for ordinary Slay contracts."""

import asyncio
import hashlib
import math
from pathlib import Path
import re

from game.veloren.settlement import native_command_text


async def initialize_contract(admin, actor, fixture: dict) -> dict:
    from scripts.rpg_benchmark import contract_evidence as evidence, native_outcomes, setup
    from scripts.rpg_benchmark.combat_support import native_binding

    commands = []
    spec = fixture["contract"]
    oracle = admin.out / "private-native-oracle.ndjson"

    async def command(name, *arguments):
        return await native_command_text(admin, commands, name, *arguments)

    async def locate(query):
        listing = await command("rtsim_npc", query, 1)
        identifiers = re.findall(r"\((\d+)\)", listing)
        if len(identifiers) != 1:
            raise RuntimeError(f"Native contract lookup lacks exactly one existing {query}")
        identifier = int(identifiers[0])
        info = await command("rtsim_info", identifier)
        await command("rtsim_tp", identifier)
        deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < deadline:
            rows = native_outcomes.read(oracle, admin.out.name)
            matches = [row for row in evidence.bindings(rows) if row.get("rtsim_uid") == identifier]
            observation = await admin.request("observe")
            if len(matches) == 1:
                public = next((row for row in observation["nearby_entities"]
                               if row["uid"] == matches[0]["uid"]), None)
                if public is not None and observation["current_site"]["loaded_chunk"] is True:
                    return {"actor": matches[0]["actor"], "uid": public["uid"],
                            "server_entity": matches[0]["server_entity"], "rtsim_uid": identifier,
                            "source_info": info, "source_site": observation["current_site"]["location_name"]}
            await asyncio.sleep(.2)
        raise RuntimeError(f"Existing {query} did not load with a unique native actor/UID binding")

    giver = await locate("civilised,guard")
    if giver["source_site"] != spec["source_site"]:
        raise RuntimeError("Native contract giver is not from the declared source settlement")
    funding = spec.get("giver_funding", 1000)
    await command("sudo", f"uid@{giver['uid']}", "give_item", "common.items.utility.coins", funding)
    await command("sudo", f"uid@{giver['uid']}", "goto", *spec["giver_position"])
    target = await locate("monster,ogre")
    await command("sudo", f"uid@{target['uid']}", "goto", *spec["target_position"])
    await command("sudo", f"uid@{giver['uid']}", "goto", *spec["giver_position"])
    opening = await setup.wait_observation(actor, lambda row: all(
        any(entry["uid"] == entity["uid"] and math.dist(entry["position"], position) < 2
            for entry in row["nearby_entities"])
        for entity, position in ((giver, spec["giver_position"]), (target, spec["target_position"]))
    ), "existing native giver and uninjured Monster placed in the authored scene")
    for entity in (giver, target):
        entity["binding"] = await native_binding(actor, entity["uid"])
        public = next(row for row in opening["nearby_entities"] if row["uid"] == entity["uid"])
        entity["player_target"] = public["control_target"]
        entity["public"] = public
        binding = entity["binding"]
        if (binding["server_entity"] != entity["server_entity"] or binding["dead"]
                or binding["health"] <= 0 or binding["health"] != binding["maximum_health"]):
            raise RuntimeError("Contract participant changed identity or lacks full native health")
    if (target["binding"]["alignment"] != "Enemy"
            or target["binding"]["body"].get("BipedLarge", {}).get("species") != "Ogre"):
        raise RuntimeError("Slay target is not the declared ordinary native Ogre")
    return {
        "giver": giver, "target": target, "commands": commands,
        "helper_sha256": hashlib.sha256(Path(evidence.__file__).read_bytes()).hexdigest(),
        "giver_funding": funding,
        "scope": f"Existing RTSim guard and Monster; initial placement and {funding} giver coins only. "
                 "No accepted quest, health reduction, AI override, safezone or post-opening assistance.",
    }


def contract_registry(prepared: dict, observation: dict, rows: list[dict]) -> dict:
    from scripts.rpg_benchmark import contract_evidence as evidence

    uid = observation["self_identity"]["uid"]
    players = [row for row in evidence.bindings(rows) if row["uid"] == uid]
    if (len(players) != 1 or players[0]["actor"] !=
            {"Character": observation["self_identity"]["native_character_id"]}):
        raise RuntimeError("Native contract player lacks a unique character/UID/entity binding")
    if observation["dialogue"] is not None or observation["dialogue_markers"]:
        raise RuntimeError("Native contract must open before player dialogue or quest directions")
    quests = evidence.latest(rows, "quest_states")
    if not isinstance(quests, list) or any(
        entry["actor"] == players[0]["actor"] for quest in quests for entry in quest["actors"]
    ):
        raise RuntimeError("Contract opening lacks fresh native quest-state evidence")
    for name in ("giver", "target"):
        entity = prepared[name]
        public = next((row for row in observation["nearby_entities"] if row["uid"] == entity["uid"]), None)
        if (public is None or public["control_target"] != entity["player_target"]
                or public["health"]["dead"] or public["health"]["current"] != entity["binding"]["maximum_health"]):
            raise RuntimeError("Native contract participant disappeared or was injured before measured play")
    if any(prepared["target"]["actor"] == entry["actor"] for quest in quests for entry in quest["actors"]):
        raise RuntimeError("Slay target already belongs to a native quest")
    return {
        "run_id": rows[0]["data"]["run_id"], "nonce": rows[0]["data"]["nonce"],
        "opening_sequence": rows[-1]["sequence"], "preexisting_quest_ids": [quest["quest_id"] for quest in quests],
        "player": {**players[0], "client_session_id": observation["session_id"],
                   "client_actor": observation["control_actor"]},
        "giver_actor": prepared["giver"]["actor"], "target_actor": prepared["target"]["actor"],
        "giver_target": prepared["giver"]["player_target"],
        "helper_sha256": prepared["helper_sha256"],
    }


def contract_snapshot(registry: dict, opening: dict, final: dict, rows: list[dict]) -> dict:
    from scripts.rpg_benchmark import contract_evidence as evidence

    if hashlib.sha256(Path(evidence.__file__).read_bytes()).hexdigest() != registry["helper_sha256"]:
        raise RuntimeError("Native contract evidence helper changed during the episode")
    candidates = {}
    for row in rows:
        if row["event"] != "quest_states" or row["sequence"] <= registry["opening_sequence"]:
            continue
        for quest in row["data"]:
            kind = quest["quest"]["kind"].get("Slay")
            if (quest["quest_id"] not in registry["preexisting_quest_ids"] and kind is not None
                    and kind["slayer"] == registry["player"]["actor"]
                    and kind["target"] == registry["target_actor"]
                    and quest["quest"]["arbiter"] == registry["giver_actor"]):
                candidates.setdefault(quest["quest_id"], {"activation_sequence": row["sequence"], "quest": quest})
    results = []
    for candidate in candidates.values():
        activation = candidate["activation_sequence"]
        results.append({
            **candidate,
            "reward": evidence.reward(rows, candidate["quest"], registry["player"], after=activation),
            "slay": evidence.slay(rows, registry["target_actor"], registry["player"], [opening, final],
                                  after=activation, run_id=registry["run_id"]),
        })
    return {"schema": "livequest-native-contract/1", "registry": registry,
            "through_sequence": rows[-1]["sequence"], "candidates": results,
            "player_deaths": evidence.player_deaths(rows, registry["player"], after=registry["opening_sequence"])}
