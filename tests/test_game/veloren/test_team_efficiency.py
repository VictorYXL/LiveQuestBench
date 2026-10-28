from copy import deepcopy
from pathlib import Path

import pytest

from game.veloren.evaluators import team_efficiency as metrics
from tests.test_game.veloren.test_itinerary import score


def test_native_travel_preserves_detours_and_team_transfers_are_not_consumption(monkeypatch):
    states = {}
    for role, uid in (("Alpha", 7), ("Beta", 8)):
        first, last = score([[3, 0, 201], [3, 4, 201]] if role == "Alpha" else [])
        last["position"] = [3, 4, 201] if role == "Alpha" else first["position"]
        for row, now in ((first, 100), (last, 115)):
            row["self_identity"]["uid"] = row["private_route_evidence"]["uid"] = uid
            row["survival"]["buff_clock"] = {"synchronized": True, "now": now}
            row["inventory"] = {"items": [], "equipment": {}}
        states[role] = first, last
    material = {"id": {"Simple": "material"}, "amount": 2}
    shirt = {"id": {"Simple": "shirt"}, "amount": 1}
    states["Alpha"][0]["inventory"].update(items=[{"item": material}], equipment={"chest": shirt})
    states["Alpha"][1]["inventory"]["items"] = [{"item": shirt}]
    states["Beta"][1]["inventory"]["items"] = [{"item": material}]
    monkeypatch.setattr(metrics, "load_pair", lambda before, after: states[before.name])
    result = metrics.team_efficiency(Path("before"), Path("after"), list(states))
    assert result["participants"]["Alpha"]["sampled_horizontal_metres"] == 7
    assert result["participants"]["Alpha"]["native_client_physics_seconds"] == 15
    assert result["participants"]["Alpha"]["possessions_net_changes"] == {"material": -2}
    assert result["participants"]["Beta"]["possessions_net_changes"] == {"material": 2}
    assert result["team_possessions_net_changes"] == {}
    changed = deepcopy(states)
    changed["Beta"][1]["survival"]["buff_clock"]["now"] = 99
    monkeypatch.setattr(metrics, "load_pair", lambda before, after: changed[before.name])
    with pytest.raises(ValueError, match="clocks"):
        metrics.team_efficiency(Path("before"), Path("after"), list(states))
