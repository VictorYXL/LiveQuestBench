"""Bounded public-control witnesses and lawful counterpolicies for the new proposal."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time

from game.minecraft.evaluators.camel_delivery import evaluate, verify_initial_materials
from game.minecraft.fixtures.camel_delivery import (
    DESTINATIONS, PUBLIC_GOAL, SOURCE, commands, on_pad, policy,
)
from game.minecraft.fixtures import camel_delivery_flush_v4
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState


def condition_spec(name):
    if name == "courier-v3":
        return {"goal": PUBLIC_GOAL, "commands": commands,
                "destinations": DESTINATIONS, "evaluate": evaluate, "top_face": False}
    if name == camel_delivery_flush_v4.VERSION:
        return {"goal": camel_delivery_flush_v4.PUBLIC_GOAL,
                "commands": camel_delivery_flush_v4.commands,
                "destinations": camel_delivery_flush_v4.DESTINATIONS,
                "evaluate": camel_delivery_flush_v4.evaluate, "top_face": True}
    raise ValueError(f"Unknown versioned courier condition: {name}")


async def aim_furnace(public, call, point, *, top_face=False):
    x, y, z = point
    for _ in range(6):
        await call("LookAtPositionTool", x=x + .5,
                   y=y + (.99 if top_face else .5), z=z + .5)
        await asyncio.sleep(.1)
        if (await public.observe())["aimed_node_coords"] == {"x": x, "y": y, "z": z}:
            return (await call("InspectFurnaceTool"))["payload"]
    raise RuntimeError("Public crosshair feedback did not acquire the furnace")


async def control(public, output, controller, *, destinations=DESTINATIONS, top_face=False):
    calls = []

    async def observe():
        return await public.observe()

    def camel(state):
        return next(e for e in state["nearby_entities"] if e["name"] == "camel")

    async def call(name, **arguments):
        result = await public.call_tool(name, arguments)
        state = await observe()
        calls.append({"name": name, "arguments": arguments, "result": result,
                      "position": state["position"], "entities": state["nearby_entities"],
                      "inventory": state["inventory"], "aimed_node_coords": state["aimed_node_coords"]})
        (output / "public-calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        if not result["success"]:
            raise RuntimeError(f"Public action refused: {name}: {result}")
        return result

    async def face(dx, dz):
        p = (await observe())["position"]
        await call("LookAtPositionTool", x=p["x"] + dx, y=p["y"] + 1.62, z=p["z"] + dz)

    async def approach(axis, target, tolerance):
        for _ in range(64):
            point = camel(await observe())["position"]
            delta = target - point[axis]
            if abs(delta) < tolerance:
                return
            if point["y"] < 71.9:
                raise RuntimeError("Entered catch during alignment; no private recovery")
            sign = 100 if delta > 0 else -100
            await face(sign if axis == "x" else 0, sign if axis == "z" else 0)
            await call("MoveTool", direction="forward",
                       duration=min(1.5, max(.05, abs(delta) / (2 * drive_rate))))
            await asyncio.sleep(.4)
        raise RuntimeError("Bounded public alignment did not converge")

    async def click(slot):
        return (await call("FurnaceClickTool", slot=slot,
                           button="left", operation="pickup"))["payload"]

    async def deliver(index):
        window = await aim_furnace(public, call, destinations[index], top_face=top_face)
        wanted = ("Pad A clay", "Pad B clay")[index]
        slot = next(s["slot"] for s in window["slots"]
                    if s["slot"] >= 3 and s["item"] is not None
                    and s["item"]["description"] == wanted)
        await click(slot)
        await click(0)
        await call("StopTool")
        await asyncio.sleep(1)

    await aim_furnace(public, call, SOURCE)
    await click(0)
    await click(30)
    await click(1)
    await click(31)
    await call("SelectTool", slot=9)
    p = camel(await observe())["position"]
    await call("LookAtPositionTool", x=p["x"], y=p["y"] + 1.2, z=p["z"])
    await call("UseHeldItemTool", duration=.1)
    await call("MoveTool", direction="forward", duration=.1)
    await asyncio.sleep(3)
    if (await observe())["position"]["y"] < 73:
        raise RuntimeError("Existing native use did not mount the courier")

    result = {"controller": controller, "landings": []}
    if controller == "adaptive":
        measurements = []
        result["public_probes"] = []
        selected = None
        for charge, direction in ((.5, 1), (.05, -1)):
            await face(direction * 100, 0)
            before = camel(await observe())["position"]
            await call("JumpTool", duration=charge)
            await asyncio.sleep(3.2)
            after = camel(await observe())["position"]
            distance = direction * (after["x"] - before["x"])
            result["public_probes"].append({
                "charge": charge, "direction": direction,
                "before": before, "after": after, "distance": distance,
            })
            (output / "public-decisions.json").write_text(json.dumps(result, indent=2) + "\n")
            if abs(after["y"] - 72) > .1:
                raise RuntimeError("Probe left the practice floor; no private recovery")
            measurements.append({"charge": charge, "distance": distance})
            selected = policy(measurements)
            if selected is not None:
                break
        if selected is None:
            raise RuntimeError("No measured charge predicts a safe application landing")
        drive_rate = max(1, measurements[0]["distance"] * .35)
        result.update(public_probe=result["public_probes"][0],
                      selected_policy=selected,
                      policy_source="current_episode_measured_displacements_and_public_geometry")
    else:
        selected = {"charge": .5, "launch_x": (.3, 7.3)}
        drive_rate = 5
    (output / "public-decisions.json").write_text(json.dumps(result, indent=2) + "\n")
    await approach("x", -2, .45)
    await approach("z", 21.6, .5)
    if controller == "cold-courier":
        await approach("x", 1.3, .15)
        await approach("z", 23.1, .15)
        await deliver(0)
        result["pad_a_delivered_before_first_dash"] = True
    for index in range(2):
        if controller in ("furnace-bumper", "cold-courier"):
            await approach("z", 21.3, .15)
        await approach("x", selected["launch_x"][index],
                       .45 if selected["charge"] < .1 else .18)
        if controller in ("furnace-bumper", "cold-courier"):
            await approach("z", 23.1, .15)
        await face(100, 0)
        launch = camel(await observe())["position"]
        if controller == "slow-walk":
            await call("MoveTool", direction="forward", duration=2)
        else:
            await call("JumpTool", duration=selected["charge"])
        await asyncio.sleep(3.2)
        landing = camel(await observe())["position"]
        result["landings"].append({"launch": launch, "landing": landing,
                                   "on_pad": on_pad(landing, index)})
        (output / "public-decisions.json").write_text(json.dumps(result, indent=2) + "\n")
        if controller == "cold-courier":
            if (11 <= landing["x"] < 15 and 20 <= landing["z"] < 24
                    and 71.9 <= landing["y"] <= 73.1):
                if landing["y"] > 72.1:
                    await approach("z", 21.3, .15)
                await deliver(1)
                result["disposition"] = "Cold fixed-charge courier endpoint reached"
                break
            # Landing on the existing furnace is legal; walk off onto its pad.
            if (index == 0 and 4 <= landing["x"] < 8 and 20 <= landing["z"] < 24
                    and 71.9 <= landing["y"] <= 73.1):
                continue
        if not on_pad(landing, index):
            result["disposition"] = "Valid native landing failure; no private recovery"
            break
        await deliver(index)
        (output / "public-decisions.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


async def run(output, base, instance, controller, condition="courier-v3"):
    spec = condition_spec(condition)
    output.mkdir(parents=True, exist_ok=False)
    (output / "public-goal.txt").write_text(spec["goal"] + "\n")
    (output / "private-authoring.json").write_text(json.dumps({
        "instance_index": instance, "selection": "predeclared_stratified_native_check",
        "controller_receives_instance": False, "native_commands_after_begin": False,
        "condition": condition,
    }, indent=2) + "\n")
    source = Path(__file__).read_bytes()
    (output / "controller.py").write_bytes(source)
    game = MinecraftGame(
        track="structured_tool", output_dir=output / "game", world_path=base,
        player_state=PlayerState(position=(-42.5, 72, 1.5), yaw=-90),
        headless=True, recording=True, recording_fps=5,
    )
    result = {"kind": "new_locomotion_calibration_native_witness", "model_calls": 0,
              "controller_sha256": hashlib.sha256(source).hexdigest(),
              "scientific_qualification": False, "controller": controller,
              "condition": condition}
    try:
        await game.start()
        assert game.phase == "ready"
        authoring = []
        for command in spec["commands"](instance):
            feedback = await game._session.server.command(command)
            authoring.append({"command": command, "feedback": feedback})
        (output / "authoring-commands.json").write_text(json.dumps(authoring, indent=2) + "\n")
        await game.save_snapshot(output / "before")
        verify_initial_materials(output / "before")
        public = game.get_agent_interface()
        await game.begin()
        started = time.monotonic()
        result["public_control"] = await control(
            public, output, controller, destinations=spec["destinations"],
            top_face=spec["top_face"],
        )
        result["active_seconds"] = time.monotonic() - started
    except Exception as error:
        result["diagnostic_error"] = f"{type(error).__name__}: {error}"
    finally:
        if game.phase == "running":
            await game.end()
            await game.save_snapshot(output / "after")
        await game.close()
        if (output / "after").exists():
            result["native_score"] = spec["evaluate"](
                output / "before", output / "after", game.player_uuid,
            )
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--instance", required=True, type=int, choices=(0, 1))
    parser.add_argument("--controller", choices=(
        "adaptive", "max-charge", "slow-walk", "furnace-bumper", "cold-courier",
    ),
                        default="adaptive")
    parser.add_argument("--condition", choices=(
        "courier-v3", camel_delivery_flush_v4.VERSION,
    ), default="courier-v3")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.base, args.instance, args.controller, args.condition))
