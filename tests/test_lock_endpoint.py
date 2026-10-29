from uuid import UUID

import nbtlib
from nbtlib import Compound, Int, Long, List, String

from game.minecraft.evaluators.target_lock import evaluate_lock
from game.minecraft.init_player_state import PlayerState


def test_tokens_do_not_replace_living_floor_return(tmp_path):
    owner = UUID(int=1)
    before, after = tmp_path/"before", tmp_path/"after"
    for path, tick in ((before, 10), (after, 100)):
        path.mkdir()
        nbtlib.File({"Data": Compound({"Time": Long(tick)})}, gzipped=True).save(path/"level.dat")
    PlayerState(position=(.5, 80, .5), inventory=[
        {"slot": 0, "item": "paper", "count": 1},
        {"slot": 1, "item": "paper", "count": 1},
    ]).write(after, owner)
    player = nbtlib.load(after/"playerdata"/f"{owner}.dat")
    for index, item in enumerate(player["Inventory"], 1):
        item["tag"] = Compound({"livequest_token": String(f"target_{index}")})
    player.save(after/"playerdata"/f"{owner}.dat")
    events = []
    for i, target in enumerate(("application_1", "application_2"), 1):
        for kind, tick in (("shot", 20*i), ("target_hit", 20*i+1)):
            event = Compound({"player": List[Int]([0,0,0,1]), "tick": Long(tick),
                              "shots": Int(i), "kind": String(kind)})
            if kind == "target_hit":
                event["target"] = String(target)
            events.append(event)
    (after/"data").mkdir()
    nbtlib.File({"data": Compound({"contents": Compound({
        "archery": Compound({"events": List[Compound](events)})})})},
        gzipped=True).save(after/"data/command_storage_livequest.dat")
    assert not evaluate_lock(before, after, owner)["success"]
    player["Pos"][1] = nbtlib.Double(72)
    player.save(after/"playerdata"/f"{owner}.dat")
    assert evaluate_lock(before, after, owner)["success"]
