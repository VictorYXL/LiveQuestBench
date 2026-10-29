from pathlib import Path

from game.minecraft.fixtures.timed_routing import timing
from scripts import prove_timed_routing as prototype


def test_capture_cells_use_native_floor_coordinates_and_original_identity(monkeypatch):
    carts = [
        {"UUID": [1], "Tags": ["original_cart_east"], "Pos": [12.359,72.0625,.5], "Motion": [0,0,0]},
        {"UUID": [2], "Tags": ["original_cart_west"], "Pos": [-11.359,72.0625,.5], "Motion": [0,0,0]},
    ]
    original = [dict(row) for row in carts]
    monkeypatch.setattr(prototype, "entities", lambda p: original if p.name == "before" else carts)
    monkeypatch.setattr(prototype.nbtlib, "load", lambda p: {
        "Inventory": [{"tag":{"livequest_cargo":name}} for name in ("east_consignment","west_consignment")],
        "Pos": [.5,72,-10.5], "Health":20})
    assert prototype.score(Path("before"),Path("after"),"owner")["native_objective_success"]
    carts[1]["UUID"] = [3]
    assert not prototype.score(Path("before"),Path("after"),"owner")["native_objective_success"]


def test_timing_does_not_confuse_authoring_or_stationary_settling_with_departure():
    rows = [
        {"tick":90,"east_pos":[0,75,20],"east_warning":1},
        {"tick":100,"east_pos":[0,75.5,20],"east_warning":0},
        {"tick":110,"east_pos":[0,75.5625,20],"east_warning":0},
        {"tick":140,"east_pos":[0,75.5625,20],"east_warning":1},
        {"tick":180,"east_pos":[0,75,18],"east_warning":1},
    ]
    result = timing(rows,100)
    assert result["east"] == {"warning_tick":40,"first_movement_tick":80}
    assert result["west"] == {"warning_tick":None,"first_movement_tick":None}
