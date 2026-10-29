import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).parents[2] / "fixtures/veloren/firing_positions_reference.py"
spec = importlib.util.spec_from_file_location("firing_positions_reference", path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def row(state="Wielding", dead=False, missing=False):
    return {"position": [18723.5, 10824, 507], "on_ground": True,
            "survival": {"health": {"dead": False}, "character_state": state},
            "nearby_entities": [] if missing else [
                {"uid": 7, "position": [18729, 10824, 501],
                 "health": {"dead": dead, "current": 0 if dead else 10}}]}


def test_last_allowed_projectile_is_observed_before_budget_exhaustion():
    observations = iter([row(), row(), row("ChargedRanged"), row(), row(dead=True)])
    calls = []
    result = reference.fire(lambda: next(observations),
                            lambda name, **args: calls.append(name), lambda *a, **k: None,
                            7, 10824, 507, sleep=lambda _: None, limit=1)
    assert result == {"shots": 1, "public_dead": True, "target_missing": False}
    assert calls == ["LookTool", "AttackTool"]


def test_release_wait_is_bounded_and_does_not_issue_new_aim_or_attack():
    observations = 0

    def observe():
        nonlocal observations
        observations += 1
        return row("ChargedRanged")

    with pytest.raises(RuntimeError, match="within the bound"):
        reference.release_and_observe(observe, sleep=lambda _: None)
    assert observations == 60


def test_disappearing_target_is_not_claimed_dead_and_shot_limit_is_preserved():
    calls = []
    result = reference.fire(lambda: row(), lambda name, **args: calls.append(name),
                            lambda *a, **k: None, 7, 10824, 507,
                            sleep=lambda _: None, limit=2)
    assert result == {"shots": 2, "public_dead": False, "target_missing": False}
    assert calls.count("AttackTool") == 2
    result = reference.fire(lambda: row(missing=True), lambda *a, **k: None,
                            lambda *a, **k: None, 7, 10824, 507)
    assert result["target_missing"] and not result["public_dead"]


def test_repositioning_refreshes_target_before_aiming():
    moves = 0
    aims = []

    def observe():
        current = row()
        if moves > 1:
            current["nearby_entities"][0]["position"][0] = 18730
        return current

    def go(*args, **kwargs):
        nonlocal moves
        moves += 1

    def act(name, **arguments):
        if name == "LookTool":
            aims.append(arguments["x"])

    reference.fire(observe, act, go, 7, 10824, 507, sleep=lambda _: None, limit=9)
    assert moves == 2
    assert aims[:-1] == [18729] * 8
    assert aims[-1] == 18730


def test_south_wall_target_is_not_fired_at_from_inside_the_ledge():
    positions = []

    def observe():
        current = row()
        current["position"] = [18723.681640625, 10827.2236328125, 507]
        current["nearby_entities"][0]["position"] = [18723.673828125, 10829.4501953125, 501]
        return current

    def go(point, **kwargs):
        positions.append(point)
        # At the recorded27.22 position a downward projectile hits the platform
        # floor before its north edge29, rather than reaching the wolf below it.
        assert 10828.6 < point[1] < 10829

    reference.fire(observe, lambda *a, **k: None, go, 7, 10824, 507,
                   sleep=lambda _: None, limit=9)
    assert positions


def test_unstable_perimeter_does_not_trigger_blind_firing():
    calls = []

    def observe():
        current = row()
        current["on_ground"] = False
        return current

    with pytest.raises(RuntimeError, match="Native footing"):
        reference.fire(observe, lambda name, **k: calls.append(name), lambda *a, **k: None,
                       7, 10824, 507, sleep=lambda _: None)
    assert "AttackTool" not in calls


def test_observed_northward_target_change_requires_immediate_new_face():
    player = [18723.884765625, 10809.4345703125, 506]
    assert not reference.needs_new_face(player, [18730.6348, 10810.5713, 501], 10808)
    assert reference.needs_new_face(player, [18723.890625, 10803.5498046875, 501], 10808)
    point = reference.firing_position([18723.890625, 10803.5498046875, 501], 10808, 506)
    assert point[1] > 10804


def test_precision_movement_settles_each_step_and_never_jumps_after_falling():
    before, after = row(), row()
    before["position"] = [18723.75, 10804.5, 506]
    after["position"] = [18723.75, 10804.25, 506]
    observations = iter([before, after])
    calls = []

    def act(name, **args):
        calls.append((name, args))
        return {"result": {"detail": {}}}

    reference.move_to(lambda: next(observations), act, after["position"],
                      tolerance=.12, sleep=lambda _: None)
    assert ("MoveTool", {"direction": "backward", "duration_ticks": 1}) in calls
    assert [name for name, _ in calls].count("StopTool") == 2
    before["position"] = [18723.60546875, 10801.4501953125, 501]
    calls.clear()
    with pytest.raises(RuntimeError, match="Lost native footing"):
        reference.move_to(lambda: before, act, after["position"],
                          tolerance=.12, sleep=lambda _: None)
    assert not any(name in {"JumpTool", "MoveTool"} for name, _ in calls)


def test_observed_forward_quantization_uses_native_backstep_for_last_centimetres():
    before, after = row(), row()
    before["position"] = [18723.466796875, 10804.3916015625, 506]
    after["position"] = [18723.46484375, 10804.216796875, 506]
    observations = iter([before, after])
    calls = []

    def act(name, **args):
        calls.append((name, args))
        return {"result": {"detail": {}}}

    reference.move_to(lambda: next(observations), act,
                      [18723.46484375, 10804.25, 506],
                      tolerance=.12, sleep=lambda _: None)
    aim = next(args for name, args in calls if name == "LookTool")
    assert aim["y"] > before["position"][1]
    assert ("MoveTool", {"direction": "backward", "duration_ticks": 1}) in calls


@pytest.mark.parametrize("positions", [[
        [18723.806640625, 10808.7822265625, 506],
        [18723.779296875, 10808.9580078125, 506],
        [18723.75, 10809.1337890625, 506],
    ], [
        [18723.75, 10808.9881640625, 506],
        [18723.75, 10808.9931640625, 506],
        [18723.75, 10809.0031640625, 506],
    ]])
def test_native_stall_diagnostic_does_not_override_observed_settled_progress(positions):
    moves = 0

    def observe():
        current = row()
        current["position"] = positions[moves]
        return current

    def act(name, **args):
        nonlocal moves
        if name == "MoveTool":
            moves += 1
            return {"result": {"status": "failed",
                               "detail": {"code": "stalled", "distance_moved": .049}}}
        return {"result": {"detail": {}}}

    reference.move_to(observe, act, [18723.75, 10809.1181640625, 506],
                      tolerance=.12, sleep=lambda _: None)
    assert moves == 2


def test_precision_stall_without_observed_progress_still_stops_after_two_moves():
    current = row()
    current["position"] = [18723.75, 10808.5, 506]
    moves = 0

    def act(name, **args):
        nonlocal moves
        if name == "MoveTool":
            moves += 1
            return {"result": {"status": "failed",
                               "detail": {"code": "stalled", "distance_moved": 0}}}
        return {"result": {"detail": {}}}

    with pytest.raises(RuntimeError, match="Public movement is blocked"):
        reference.move_to(lambda: current, act, [18723.75, 10809, 506],
                          tolerance=.12, sleep=lambda _: None)
    assert moves == 2
