"""Small offline admission checks; no provider requests or game startup."""

from copy import deepcopy
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

import nbtlib
import yaml

from benchmark.config import ConfigError, load_task
from benchmark.factory import make_game
from game.minecraft.evaluators.cargo import evaluate_cargo, verify_initial_cargo
from game.minecraft.evaluators.world import read_block_entity


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--reference", type=Path)
args = parser.parse_args()


source = Path("config/minecraft/tasks/structured_tools/abandoned_mine_cargo.yaml")
st = load_task(source)
vm = load_task(Path("config/minecraft/tasks/visual_motor/abandoned_mine_cargo.yaml"))
assert st.task == vm.task and st.fixture == vm.fixture
assert st.evaluator_parameters == vm.evaluator_parameters
assert st.capabilities == vm.capabilities
assert st.capabilities.primary == ("spatial_interaction",)
assert st.resolved()["capabilities"]["primary"] == ("spatial_interaction",)
assert "GoToPositionTool" not in st.tools
assert "SmeltItemTool" not in st.tools
for task in (st, vm):
    make_game(task, Path("unused-admission"), headless=True, recording=False, recording_fps=5)

data = yaml.safe_load(source.read_text())
with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
    path = Path(temporary) / "task.yaml"
    for metadata in (
        {"primary": []}, {"primary": ["unknown"]},
        {"primary": ["spatial_interaction"], "secondary": ["spatial_interaction"]},
        {"primary": ["spatial_interaction"], "hidden_weight": 5},
    ):
        row = {**data, "capabilities": metadata}
        path.write_text(yaml.safe_dump(row))
        try:
            load_task(path)
        except ConfigError:
            pass
        else:
            raise AssertionError(f"Invalid metadata was admitted: {metadata}")
    old = deepcopy(data)
    old.pop("capabilities")
    path.write_text(yaml.safe_dump(old))
    assert "capabilities" not in load_task(path).resolved()
if args.reference:
    before, after = args.reference / "before", args.reference / "after"
    player_file, = (after / "playerdata").glob("*.dat")
    player = UUID(player_file.stem)
    parameters = st.evaluator_parameters
    assert evaluate_cargo(before, after, player, **parameters)["success"]
    assert not evaluate_cargo(before, before, player, **parameters)["success"]
    original = nbtlib.load(player_file)
    with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
        ending = Path(temporary)
        (ending / "playerdata").mkdir()
        for defect in ("missing_cargo", "ordinary_replacement", "wrong_height", "dead", "airborne"):
            native = deepcopy(original)
            if defect in ("missing_cargo", "ordinary_replacement"):
                stack = next(stack for stack in native["Inventory"]
                             if str(stack.get("tag", {}).get("livequest_cargo", "")) == "lower_excavation")
                if defect == "missing_cargo":
                    native["Inventory"].remove(stack)
                else:
                    del stack["tag"]["livequest_cargo"]
            elif defect == "wrong_height":
                native["Pos"][1] = nbtlib.Double(82)
            elif defect == "dead":
                native["Health"] = nbtlib.Float(0)
            else:
                native["OnGround"] = nbtlib.Byte(0)
            native.save(ending / "playerdata" / player_file.name)
            assert not evaluate_cargo(before, ending, player, **parameters)["success"], defect
    broken = deepcopy(read_block_entity(before, tuple(parameters["cargo"][0]["chest"])))
    broken["Items"] = nbtlib.List[nbtlib.Compound]()
    with patch("game.minecraft.evaluators.cargo.read_block_entity", return_value=broken):
        try:
            verify_initial_cargo(before, player, **parameters)
        except ValueError:
            pass
        else:
            raise AssertionError("An impossible missing-cargo opening was admitted")
print(json.dumps({"paired_task_admission": True, "capability_validation": True,
                  "legacy_metadata_compatibility": True,
                  "native_scoring_negative_cases": bool(args.reference), "model_calls": 0}))
