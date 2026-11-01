"""Unprotected native Message preoffer and exact passive contract-party joins."""

import asyncio
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import time

from game.veloren.settlement import native_command_text
from game.veloren.native_bindings import NativeBindingCursor


async def prepare_initial_message_offer(admin, actor, residents, fixture, command, load_resident,
                                        prepared, helper, setup):
    spec = fixture["message_contract"]
    protocol = spec.get("initialization_protocol", "initial-message-v2")
    source, *others = residents

    async def request(operation, *arguments):
        async with asyncio.timeout(10):
            while True:
                try:
                    text = await command("rtsim_info", protocol, operation, *arguments)
                    break
                except RuntimeError as error:
                    if (protocol != "initial-message-v3" or operation != "publish"
                            or str(error) != "Native Message initialization: native_message_source_not_quiescent"):
                        raise
                    # This native refusal precedes mutation; retain the same prepared proposal.
                    await asyncio.sleep(.1)
        responses = []
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("protocol") == protocol:
                responses.append(row)
        if len(responses) != 1:
            raise RuntimeError(f"Native initial Message {operation} failed: {text}")
        result = responses[0]
        expected = {"prepare": "prepared", "publish": "published", "close": "closed"}[operation]
        if result.get("protocol") != protocol or result.get("phase") != expected:
            raise RuntimeError("Native initial Message protocol response mismatch")
        return result

    current = await actor.request("observe")
    proposal = await request("prepare", source["uid"], current["self_identity"]["uid"],
                             *(resident["uid"] for resident in others))
    ticket = proposal["proposal_id"]
    prepared["initialization_protocol"] = {"prepare": proposal}
    try:
        recipient = await load_resident(proposal["recipient_rtsim_uid"], spec["recipient_position"])
        if recipient["name_text"].rsplit(" (", 1)[0] != proposal["recipient_name"]:
            raise RuntimeError("Native prepared Message recipient identity changed")
        await command("sudo", f"uid@{recipient['uid']}", "give_item", "common.items.utility.coins", 3000)
        for resident, point in [(recipient, spec["recipient_position"]),
                                *zip(others, spec["distractor_positions"])]:
            await command("sudo", f"uid@{resident['uid']}", "goto", *point)
        await setup.goto(admin, actor, fixture["player_state"]["position"])
        if protocol == "initial-message-v3":
            publication = await request("publish", ticket, *spec["giver_position"])
        else:
            # V2 retains its separate late placement; v3 commits it atomically on the server.
            await command("sudo", f"uid@{source['uid']}", "goto", *spec["giver_position"])
            publication = await request("publish", ticket)
        prepared["initialization_protocol"]["publish"] = publication
        offer = await helper.prompt(actor)
        for _ in range(8):
            if offer["kind"] != "Statement":
                break
            await helper.dialogue_action(actor, offer)
            offer = await helper.prompt(actor, (offer["dialogue_id"], offer["tag"]))
        name = helper.plain(offer["content"].get("Localized", {}).get("args", {}).get("name"))
        if (offer["kind"] != "Question" or offer["sender_uid"] != source["uid"]
                or helper.key(offer["content"]) != "npc-response-quest-messenger-ask"
                or name != proposal["recipient_name"]):
            raise RuntimeError("Native initial Message publication is not the selected genuine offer")
        prepared.update(offer=offer, recipient={
            "rtsim_uid": proposal["recipient_rtsim_uid"], "name_text": proposal["recipient_name"]},
            offer_observed_at_ns=time.monotonic_ns(), loaded_recipient=recipient)
    finally:
        prepared["initialization_protocol"]["close"] = await request("close", ticket)


async def prepare_message_offer(actor, source, recipients, stage, prepared, helper):
    for _ in range(32):
        await stage()
        current = await actor.request("observe")
        speaker = next(entry for entry in current["nearby_entities"] if entry["uid"] == source["uid"])
        question = await helper.menu(actor, speaker)
        request = next((choice for choice in question["responses"]
                        if helper.key(choice["content"]) == "dialogue-question-quest_req"), None)
        if request is None:
            raise RuntimeError("Native resident has no ordinary quest-request option")
        await helper.dialogue_action(actor, question, request)
        offer = await helper.prompt(actor, (question["dialogue_id"], question["tag"]))
        for _ in range(8):
            if offer["kind"] != "Statement":
                break
            await helper.dialogue_action(actor, offer)
            offer = await helper.prompt(actor, (offer["dialogue_id"], offer["tag"]))
        else:
            raise RuntimeError("Native Message preoffer exceeded its statement bound")
        name = helper.plain(offer["content"].get("Localized", {}).get("args", {}).get("name"))
        matches = [entry for entry in recipients if entry["name_text"] == name]
        selected = helper.key(offer["content"]) == "npc-response-quest-messenger-ask" and len(matches) == 1
        prepared.setdefault("offer_qualification", []).append({"offer": offer, "selected": selected})
        if selected:
            prepared.update(offer=offer, giver=speaker, recipient=matches[0],
                            offer_observed_at_ns=time.monotonic_ns())
            return
        reject = next((choice for choice in offer["responses"]
                       if helper.key(choice["content"]) == "common-no"), None)
        if reject is None:
            raise RuntimeError("Unselected native quest lacks an ordinary decline response")
        await helper.dialogue_action(actor, offer, reject)
    raise RuntimeError("Bounded ordinary requests produced no uniquely identified native Message offer")


async def initialize_message(admin, actor, fixture):
    from scripts.rpg_benchmark import contract_evidence as evidence, npc_contracts, setup

    commands = []
    oracle = admin.out / "private-native-oracle.ndjson"
    spec = fixture["message_contract"]

    async def command(name, *arguments):
        initial_protocol = (name == "rtsim_info" and arguments[:1] in
                            (("initial-message-v2",), ("initial-message-v3",)))
        try:
            text = await native_command_text(admin, commands, name, *arguments)
            if initial_protocol:
                async with asyncio.timeout(10):
                    while arguments[0] not in text:
                        await asyncio.sleep(.1)
                        events = await admin.request("events")
                        commands[-1]["events"].extend(events)
                        errors = [event["data"].get("content", {}).get("Plain", "")
                                  for event in events
                                  if event.get("data", {}).get("kind") == "command_error"]
                        if errors:
                            raise RuntimeError("Native Message initialization: " + "; ".join(errors))
                        text += "\n" + "\n".join(
                            event["data"].get("content", {}).get("Plain", "") for event in events
                            if event.get("data", {}).get("kind") == "command_info")
            return text
        except RuntimeError as error:
            if initial_protocol and commands:
                errors = [event["data"].get("content", {}).get("Plain", "")
                          for event in commands[-1]["events"]
                          if event.get("data", {}).get("kind") == "command_error"]
                if errors:
                    raise RuntimeError("Native Message initialization: " + "; ".join(errors)) from error
            raise

    listing = await command("rtsim_npc", "civilised,farmer", 3)
    identifiers = re.findall(r"\((\d+)\)", listing)
    if len(identifiers) != 3 or len(set(identifiers)) != 3:
        raise RuntimeError("Message fixture requires three distinct existing native farmers")
    listing = await command("rtsim_npc", "civilised")
    catalog = re.findall(r"([^,\n]+) \((\d+)\)(?:,|$)", listing)
    names = Counter(name.strip() for name, _ in catalog)
    recipients = [{"name_text": name.strip(), "rtsim_uid": int(identifier)}
                  for name, identifier in catalog
                  if identifier not in identifiers and names[name.strip()] == 1]
    if not recipients and spec.get("initialization_protocol") not in ("initial-message-v2", "initial-message-v3"):
        raise RuntimeError("Native population lacks uniquely named Message recipients")
    cursor = NativeBindingCursor(oracle, admin.out.name)
    x, y, z = spec["giver_position"]
    staging = [[x, y, z], [x + 3, y, z], [x, y + 3, z]]

    async def load_resident(identifier, point):
        await command("rtsim_tp", identifier)
        for _ in range(200):
            matches = [entry for entry in await asyncio.to_thread(cursor.poll)
                       if entry.get("rtsim_uid") == int(identifier)]
            observation = await admin.request("observe")
            npc = next((entry for entry in observation["nearby_entities"]
                        if len(matches) == 1 and entry["uid"] == matches[0]["uid"]), None)
            if npc is not None:
                # Keep this incarnation in the player's loaded region before fetching another.
                await command("sudo", f"uid@{npc['uid']}", "goto", *point)
                return {**matches[0], "name_text": npc["name_text"]}
            await asyncio.sleep(.2)
        raise RuntimeError("Existing Message participant did not load")

    residents = [await load_resident(identifier, point)
                 for identifier, point in zip(identifiers, staging)]
    source = residents[0]
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    for resident, point in zip(residents, staging):
        await command("sudo", f"uid@{resident['uid']}", "give_item", "common.items.utility.coins", 3000)
        await command("sudo", f"uid@{resident['uid']}", "goto", *point)
    await setup.wait_observation(actor, lambda row: all(
        any(entry["uid"] == resident["uid"] for entry in row["nearby_entities"])
        for resident in residents), "unprotected existing Message participants visible")
    preoffer = {
        "case": "T11", "oracle_path": str(oracle), "run_id": admin.out.name,
    }
    async def stage_offer():
        # A distinct fixed player point avoids both floor-edge drift and NPC body collisions.
        for resident, point in [*zip(residents[1:], staging[1:]), (source, staging[0])]:
            await command("sudo", f"uid@{resident['uid']}", "goto", *point)
        await setup.goto(admin, actor, fixture["player_state"]["position"])

    if spec.get("initialization_protocol") in ("initial-message-v2", "initial-message-v3"):
        await asyncio.wait_for(prepare_initial_message_offer(
            admin, actor, residents, fixture, command, load_resident, preoffer, npc_contracts, setup), 120)
        recipient = preoffer.pop("loaded_recipient")
        return {
            "giver": source, "recipient": recipient, "distractors": residents[1:],
            "offer": preoffer["offer"], "commands": commands, "offer_qualification": [],
            "initialization_protocol": preoffer["initialization_protocol"],
            "preparation_timing": {
                "offer_observed_at_ns": preoffer["offer_observed_at_ns"],
                "participants_staged_at_ns": time.monotonic_ns(),
            },
            "recipient_selection": {
                "offered_existing_resident": preoffer["recipient"],
                "scope": "Private native initialization selection, never an Agent identity feed.",
            },
            "helper_sha256": hashlib.sha256(Path(evidence.__file__).read_bytes()).hexdigest(),
            "scope": "Versioned initialization-only genuine native Message proposal. No accepted "
                     "quest before public yes, no changed default random offers or public privilege.",
        }
    await asyncio.wait_for(
        prepare_message_offer(actor, source, recipients, stage_offer, preoffer, npc_contracts), 120)
    # Native offers sample the regional population, not the three nearest actors.
    # Fetch the uniquely named existing recipient only before opening public play.
    recipient = await load_resident(preoffer["recipient"]["rtsim_uid"], spec["recipient_position"])
    if recipient["name_text"].rsplit(" (", 1)[0] != preoffer["recipient"]["name_text"]:
        raise RuntimeError("Loaded native Message recipient does not match the offered identity")
    await command("sudo", f"uid@{recipient['uid']}", "give_item", "common.items.utility.coins", 3000)
    others = residents[1:]
    residents.append(recipient)
    for resident, point in [(source, spec["giver_position"]), (recipient, spec["recipient_position"]),
                            *zip(others, spec["distractor_positions"])]:
        await command("sudo", f"uid@{resident['uid']}", "goto", *point)
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    # Validate all four residents from the existing opening snapshot instead of
    # rereading the entire growing oracle four times while the native offer ages.
    return {
        "giver": source, "recipient": recipient, "distractors": others, "offer": preoffer["offer"],
        "commands": commands, "offer_qualification": preoffer.get("offer_qualification", []),
        "preparation_timing": {
            "offer_observed_at_ns": preoffer["offer_observed_at_ns"],
            "participants_staged_at_ns": time.monotonic_ns(),
        },
        "recipient_selection": {
            "offered_existing_resident": preoffer["recipient"],
            "scope": "Unique native name resolved before readiness, never a player-visible identity feed.",
        },
        "helper_sha256": hashlib.sha256(Path(evidence.__file__).read_bytes()).hexdigest(),
        "scope": "Existing native residents, finite initial native funding and placement; ordinary "
                 "unaccepted Message offer only. No safezone, accepted quest, NPC protection, "
                 "AI override or post-readiness relocation.",
    }


def opening_participants(prepared, observation, bindings):
    offer = prepared["offer"]
    current = observation.get("dialogue") or {}
    if (current.get("kind") != "Question"
            or str(current.get("dialogue_id")) != str(offer["dialogue_id"])
            or current.get("tag") != offer["tag"]
            or current.get("sender_uid") != prepared["giver"]["uid"]
            or current.get("content") != offer["content"]):
        raise RuntimeError("Native Message offer changed or expired before opening")
    participants = []
    for resident in [prepared["giver"], prepared["recipient"], *prepared["distractors"]]:
        matches = [binding for binding in bindings if binding["uid"] == resident["uid"]]
        if (len(matches) != 1
                or matches[0]["server_entity"] != resident["server_entity"]
                or matches[0]["dead"] or matches[0]["health"] <= 0):
            raise RuntimeError("Message opening lacks a unique living participant incarnation")
        participants.append({**resident, "binding": matches[0]})
    return participants


def message_registry(prepared, observation, rows):
    from scripts.rpg_benchmark import contract_evidence as evidence

    actor = {"Character": observation["self_identity"]["native_character_id"]}
    players = [entry for entry in evidence.bindings(rows)
               if entry["uid"] == observation["self_identity"]["uid"] and entry["actor"] == actor]
    quests = evidence.latest(rows, "quest_states")
    if len(players) != 1 or not isinstance(quests, list):
        raise RuntimeError("Message opening lacks unique native player and quest registry")
    if any(entry["actor"] == actor for quest in quests for entry in quest["actors"]):
        raise RuntimeError("Message task must open without a player-accepted contract")
    offer = prepared["offer"]
    choices = [choice for choice in offer["responses"]
               if choice["content"].get("Localized", {}).get("key") == "common-yes"]
    if len(choices) != 1 or offer["content"].get("Localized", {}).get("key") != "npc-response-quest-messenger-ask":
        raise RuntimeError("Opening is not an ordinary native Message acceptance question")
    participants = opening_participants(
        prepared, observation, evidence.latest(rows, "combat_entity_bindings", {}).get("bindings", []))
    protocol = None
    if prepared.get("initialization_protocol") is not None:
        protocol = verify_initial_message_protocol(prepared, rows, players[0]["actor"])
    return {
        "schema": "livequest-message-contract/1", "run_id": rows[0]["data"]["run_id"],
        "nonce": rows[0]["data"]["nonce"], "opening_sequence": rows[-1]["sequence"],
        "preexisting_quest_ids": [quest["quest_id"] for quest in quests],
        "player": players[0], "giver": participants[0], "recipient": participants[1],
        "offer": offer, "yes_response_id": choices[0]["response_id"],
        "helper_sha256": prepared["helper_sha256"],
        "initialization_protocol": protocol,
    }


def verify_initial_message_protocol(prepared, rows, player):
    version = prepared["initialization_protocol"]["prepare"].get("protocol", "initial-message-v2")
    if version not in ("initial-message-v2", "initial-message-v3"):
        raise RuntimeError("Unknown native Message initialization protocol")
    phases = {}
    for phase in ("prepared", "published", "closed"):
        matches = [row for row in rows if row["event"] == version.replace("-", "_") + "_" + phase]
        if len(matches) != 1:
            raise RuntimeError("Native Message initialization lacks one-shot publication/revocation")
        phases[phase] = matches[0]
    if not phases["prepared"]["sequence"] < phases["published"]["sequence"] < phases["closed"]["sequence"]:
        raise RuntimeError("Native Message initialization phases are out of order")
    proposal = phases["prepared"]["data"]
    instance = proposal["instance"]
    if (proposal["proposal_id"] != phases["published"]["data"]["proposal_id"]
            or proposal != prepared["initialization_protocol"]["prepare"]
            or instance.get("kind") != "Message"
            or instance.get("source_actor") != prepared["giver"]["actor"]
            or instance.get("target_actor") != prepared["recipient"]["actor"]
            or instance.get("messenger") != player):
        raise RuntimeError("Native Message proposal identity is not the opening participant binding")
    if version == "initial-message-v3":
        publication, closure = (phases[key]["data"] for key in ("published", "closed"))
        distances = [row.get("source_player_distance") for row in (publication, closure)]
        if (publication.get("atomic_placement") is not True
                or publication.get("normal_talk_active") is not True
                or closure.get("ready") is not True
                or any(row.get("setup_hold_active") is not False for row in (publication, closure))
                or any(type(distance) not in (int, float) or not math.isfinite(distance)
                       or not 0 <= distance < 5 for distance in distances)):
            raise RuntimeError("Atomic Message publication lacks ordinary in-range readiness")
    return {"version": version, "phases": phases}


def message_snapshot(registry, rows):
    from scripts.rpg_benchmark import contract_evidence as evidence

    if hashlib.sha256(Path(evidence.__file__).read_bytes()).hexdigest() != registry["helper_sha256"]:
        raise RuntimeError("Native Message evidence helper changed")
    candidates, accepted = {}, []
    for row in rows:
        if row["sequence"] <= registry["opening_sequence"]:
            continue
        if row["event"] == "validated_dialogue":
            data = row["data"]
            dialogue = data["dialogue"]
            response = dialogue["kind"].get("Response", {}) if isinstance(dialogue["kind"], dict) else {}
            if (data["sender_uid"] == registry["player"]["uid"]
                    and data["recipient_uid"] == registry["giver"]["uid"]
                    and str(dialogue["id"]) == str(registry["offer"]["dialogue_id"])
                    and response.get("tag") == registry["offer"]["tag"]
                    and response.get("response_id") == registry["yes_response_id"]):
                accepted.append(row["sequence"])
        elif row["event"] == "quest_states":
            for quest in row["data"]:
                instance = quest["quest"]["kind"].get("Courier", {}).get("instance", {})
                if (quest["quest_id"] not in registry["preexisting_quest_ids"]
                        and instance.get("kind") == "Message"
                        and instance.get("messenger") == registry["player"]["actor"]
                        and instance.get("source_actor") == registry["giver"]["actor"]
                        and instance.get("target_actor") == registry["recipient"]["actor"]
                        and quest["quest"]["arbiter"] == registry["recipient"]["actor"]):
                    candidates.setdefault(quest["quest_id"], {
                        "quest": quest, "activation_sequence": row["sequence"],
                    })
    for candidate in candidates.values():
        candidate["reward"] = evidence.reward(
            rows, candidate["quest"], registry["player"], after=candidate["activation_sequence"])
    return {"registry": registry, "through_sequence": rows[-1]["sequence"],
            "ordinary_acceptance_sequences": accepted, "candidates": list(candidates.values())}
