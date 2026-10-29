import pytest

from game.minecraft.fixtures.function_replication import score, count_removals
from game.minecraft.runtime.observed_server import ObservedServer


def events():
    return [
        {"station": station, "a": a, "b": b, "lit": int(a and b), "tick": 100,
         "connections": [] if station == 0 else [[station, 72, 0]]}
        for station in range(3) for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))
    ]


def test_native_equivalence_requires_all_cases_and_unchanged_construction():
    final = [[[1, 72, 0]], [[2, 72, 0]]]
    assert score(events(), start_tick=90, final_connections=final)["native_function_match"]
    assert not score(events()[:-1], start_tick=90, final_connections=final)["native_function_match"]
    changed = events()
    changed[-1]["connections"] = [[2, 72, 1]]
    assert not score(changed, start_tick=90, final_connections=final)["native_function_match"]


def test_constant_output_and_changing_reference_do_not_pass():
    final = [[[1, 72, 0]], [[2, 72, 0]]]
    wrong = events()
    wrong[-2]["lit"] = 1
    assert not score(wrong, start_tick=90, final_connections=final)["native_function_match"]
    contradictory = events() + [{"station": 0, "a": 0, "b": 0, "lit": 1, "tick": 101}]
    with pytest.raises(ValueError, match="changed"):
        score(contradictory, start_tick=90, final_connections=final)
    dead = events()
    for event in dead:
        event["lit"] = 0
    result = score(dead, start_tick=90, final_connections=final)
    assert not result["fixture_function_valid"] and not result["native_function_match"]


def test_observer_fabric_console_preserves_vanilla_admin_barriers():
    fabric = '[16:41:15] [Server thread/INFO] (Minecraft) Done (1.432s)! For help, type "help"'
    assert ObservedServer.normalize_console_line(fabric) == fabric.replace("] (Minecraft) ", "]: ")
    barrier = '[16:41:16] [Server thread/INFO] (Minecraft) Storage gameagent:runner has the following contents: "abc"'
    assert "[Server thread/INFO]: Storage gameagent:runner" in ObservedServer.normalize_console_line(barrier)
    other = '[16:41:15] [Server thread/INFO] (OtherMod) Done (1s)! For help, type "help"'
    assert ObservedServer.normalize_console_line(other) == other


def test_rewiring_invalidates_earlier_case_evidence():
    rows = events() + [
        {"station": 1, "a": 0, "b": 0, "lit": 0, "tick": 101, "connections": []},
        {"station": 1, "a": 0, "b": 0, "lit": 0, "tick": 102, "connections": [[1,72,0]]},
    ]
    assert not score(rows, start_tick=90, final_connections=[[[1,72,0]],[[2,72,0]]])["native_function_match"]


def test_repeated_owned_breaks_count_even_outside_old_blueprint_regions():
    event = {"schema": "livequest-native-successful-break/1", "player_uuid": "owner",
             "native_tick": 100, "old_block_id": "minecraft:cobblestone", "x": -25, "y": 72, "z": 3}
    result = count_removals([event]*7, "owner", start_tick=90, end_tick=110)
    assert result == {"successful_removals": 7, "within_six_removal_budget": False}
