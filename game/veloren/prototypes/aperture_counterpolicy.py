"""Cold finite aiming sweep using only public positions, health and fixed task instructions."""

import asyncio
import math


class PolicyStop(RuntimeError):
    pass


def firing_position(slot, target_position, front):
    tx, ty, _ = target_position
    if ty <= front + 1:
        return None
    x = slot + (slot - tx) * 4.5 / (ty - front - .5)
    if not 18702.5 <= x <= 18725.5:
        return None
    return [x, front - 4]


async def settled_navigation(observe, action, destination, *, sleep=asyncio.sleep, pulse_log=None):
    gains = []
    previous_pulse = None
    for _ in range(100):
        await action("StopTool")
        await sleep(.25)
        row = await observe()
        if row["survival"]["health"]["dead"]:
            raise PolicyStop("Public player death")
        position = row["position"]
        if abs(position[2] - 501) > .35:
            raise PolicyStop("Public position left the published platform floor")
        distance = math.dist(position[:2], destination[:2])
        speed = math.hypot(*row["velocity"][:2])
        if speed > .15 or not row["on_ground"]:
            continue
        if previous_pulse is not None:
            origin, ticks = previous_pulse
            moved = math.dist(origin, position[:2])
            if moved > .01:
                gains.append(moved / ticks)
                gains = gains[-8:]
            previous_pulse = None
        if distance <= .15:
            return row
        ticks = (max(1, min(4, math.floor(.45 * distance / max(gains))))
                 if gains else 1)
        if pulse_log is not None:
            pulse_log.append({
                "public_position": position, "destination": destination,
                "settled_metres_per_update": list(gains), "duration_ticks": ticks,
            })
        await action("LookTool", x=destination[0], y=destination[1], z=position[2])
        previous_pulse = (position[:2], ticks)
        await action("MoveTool", direction="forward", duration_ticks=ticks)
    raise PolicyStop("Settled public navigation bound exhausted")


async def cold_sweep(observe, action, result, *, retain_feedback=False):
    opening = await observe()
    result["opening_public_legooms"] = [
        row["uid"] for row in opening["nearby_entities"]
        if row.get("name_text") == "Green Legoom"
    ]
    result["policy"] = {
        "kind": ("within_episode_public_feedback_sweep" if retain_feedback
                 else "cold_per_structure_public_body_aim_sweep"),
        "controller_revision": 6,
        "retained_practice_mapping": retain_feedback,
        "slot_order": [18709.5, 18712.5, 18715.5],
        "aim_offsets_below_public_target_feet": [1.4, 1.0, 1.8],
        "scope": "A finite legal counterpolicy, not an exhaustive solver or causal learning comparison.",
        "geometry_inputs": "Published slot centers, fronts and exterior lanes; own pose, velocity and target positions from current public observations only. No private rear-window or fixture input.",
        "recovery": "Within the existing ten-attempt bound, retain a locally observed slot/aim pair after intermittent nondamaging feedback; ordinary waiting only, no reset or refill.",
        "motor_units": "Native client updates are not seconds. Calibrate settled displacement from public observations, start with one update, and reject off-floor arrivals. Published floor z501 is controller input, not a new game scoring restriction.",
    }

    async def navigate(destination):
        row = await settled_navigation(observe, action, destination,
                                       pulse_log=result.setdefault("navigation_pulses", []))
        result.setdefault("settled_arrivals", []).append({
            "destination": destination, "public_position": row["position"],
            "public_velocity": row["velocity"],
        })

    result["structures"] = []
    retained_slot = None
    retained_offset = None
    for front in (10810, 10832):
        await action("WieldTool", wield=False)
        if front == 10832:
            await navigate([18702.5, 10806])
            await navigate([18702.5, 10828])
        await navigate([18712.5, front - 4])
        row = await observe()
        targets = [entry for entry in row["nearby_entities"]
                   if entry.get("name_text") == "Green Legoom" and entry.get("health")
                   and not entry["health"]["dead"]
                   and front + 4 < entry["position"][1] < front + 15]
        if len(targets) != 1:
            raise PolicyStop("Original-looking public target absent or ambiguous")
        uid = targets[0]["uid"]
        stage = {"front": front, "public_uid": uid, "public_damage_seen": False,
                 "shot_requests": 0, "native_emitted_shots": "not_measured"}
        result["structures"].append(stage)
        finished = False
        slots = [18709.5, 18712.5, 18715.5]
        if retain_feedback and retained_slot is not None:
            slots.remove(retained_slot)
            slots.insert(0, retained_slot)
        stage["slot_order"] = slots
        for slot in slots:
            offsets = [1.4, 1.0, 1.8]
            if slot == retained_slot and retained_offset in offsets:
                offsets.remove(retained_offset)
                offsets.insert(0, retained_offset)
            stage.setdefault("aim_offset_order_by_slot", {})[str(slot)] = offsets
            row = await observe()
            enemy = next((entry for entry in row["nearby_entities"] if entry["uid"] == uid), None)
            if enemy is None:
                finished = stage["public_damage_seen"]
                break
            destination = firing_position(slot, enemy["position"], front)
            if destination is None:
                stage.setdefault("skipped_unsupported_candidates", []).append({
                    "slot": slot, "public_target_position": enemy["position"],
                })
                continue
            await action("WieldTool", wield=False)
            await navigate(destination)
            await action("WieldTool", wield=True)
            for offset in offsets:
                for attempt in range(10):
                    row = await observe()
                    enemy = next((entry for entry in row["nearby_entities"] if entry["uid"] == uid), None)
                    if enemy is None or enemy["health"]["dead"]:
                        finished = stage["public_damage_seen"]
                        break
                    destination = firing_position(slot, enemy["position"], front)
                    if destination is None:
                        stage.setdefault("skipped_unsupported_candidates", []).append({
                            "slot": slot, "public_target_position": enemy["position"],
                        })
                        break
                    if (math.dist(row["position"][:2], destination) > .15
                            or math.hypot(*row["velocity"][:2]) > .15):
                        await navigate(destination)
                        row = await observe()
                        enemy = next((entry for entry in row["nearby_entities"]
                                      if entry["uid"] == uid), None)
                        if enemy is None:
                            finished = stage["public_damage_seen"]
                            break
                    health = enemy["health"]["current"]
                    x, y, z = enemy["position"]
                    await action("LookTool", x=x, y=y, z=z - offset)
                    await action("AttackTool", channel="primary", duration_ticks=60)
                    stage["shot_requests"] += 1
                    await asyncio.sleep(.3)
                    row = await observe()
                    after = next((entry for entry in row["nearby_entities"] if entry["uid"] == uid), None)
                    if after is None:
                        stage["public_target_disappeared_not_death_proof"] = True
                        finished = stage["public_damage_seen"]
                        break
                    if after["health"]["current"] < health:
                        stage["public_damage_seen"] = True
                        stage["slot_during_public_health_drop"] = slot
                        stage["aim_offset_during_public_health_drop"] = offset
                        stage.setdefault("first_feedback_slot", slot)
                        stage.setdefault("first_feedback_aim_offset", offset)
                    elif (stage.get("first_feedback_slot"),
                          stage.get("first_feedback_aim_offset")) != (slot, offset):
                        break
                    else:
                        stage["nondamaging_feedback_retries"] = stage.get(
                            "nondamaging_feedback_retries", 0) + 1
                        await asyncio.sleep(.35)
                if finished:
                    break
            if finished:
                break
        if not finished:
            raise PolicyStop("Finite public slot/aim sweep did not complete this target")
        stage["public_completion_hint_not_native_death_proof"] = True
        if retain_feedback:
            retained_slot = stage.get("first_feedback_slot")
            retained_offset = stage.get("first_feedback_aim_offset")
    await action("StopTool")
