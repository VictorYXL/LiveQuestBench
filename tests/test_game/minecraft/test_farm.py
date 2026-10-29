from io import BytesIO
from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators.farm import saved_alive_sheep, surviving_offspring


def test_only_the_bred_child_can_satisfy_survival():
    evidence = {"events": [{"player": [0, 0, 0, 1], "tick": 20, "captured_tick": 21,
                            "children": [[1, 2, 3, 4]]}],
                "alive": [[9, 9, 9, 9]]}
    assert not surviving_offspring(evidence, UUID(int=1), 10, 30)
    evidence["alive"].append([1, 2, 3, 4])
    assert surviving_offspring(evidence, UUID(int=1), 10, 30) == [[1, 2, 3, 4]]


@pytest.mark.parametrize("children", [[], [[1, 2, 3, 4], [4, 3, 2, 1]]])
def test_ambiguous_breeding_evidence_is_invalid_not_success(children):
    evidence = {"events": [{"player": [0, 0, 0, 1], "tick": 20, "captured_tick": 21,
                            "children": children}], "alive": children}
    with pytest.raises(ValueError, match="ambiguous"):
        surviving_offspring(evidence, UUID(int=1), 10, 30)


@pytest.mark.parametrize("captured_tick,last", [(20, 30), (22, 30), (21, 20)])
def test_prebirth_delayed_or_post_snapshot_capture_is_invalid(captured_tick, last):
    evidence = {"events": [{"player": [0, 0, 0, 1], "tick": 20, "captured_tick": captured_tick,
                            "children": [[1, 2, 3, 4]]}], "alive": [[1, 2, 3, 4]]}
    with pytest.raises(ValueError, match="exactly one"):
        surviving_offspring(evidence, UUID(int=1), 10, last)


@pytest.mark.parametrize("health,expected", [(8.0, [[1, 2, 3, 4]]), (0.0, [])])
def test_saved_passenger_survival_does_not_depend_on_loaded_tick_sample(tmp_path, health, expected):
    child = nbtlib.Compound({
        "id": nbtlib.String("minecraft:sheep"), "UUID": nbtlib.IntArray([1, 2, 3, 4]),
        "Health": nbtlib.Float(health),
    })
    boat = nbtlib.Compound({
        "id": nbtlib.String("minecraft:boat"),
        "Passengers": nbtlib.List[nbtlib.Compound]([child]),
    })
    chunk = nbtlib.File({
        "DataVersion": nbtlib.Int(3700), "Position": nbtlib.IntArray([0, 0]),
        "Entities": nbtlib.List[nbtlib.Compound]([boat]),
    })
    buffer = BytesIO()
    chunk.write(buffer)
    payload = b"\x03" + buffer.getvalue()
    folder = tmp_path / "DIM-1/entities"
    folder.mkdir(parents=True)
    (folder / "r.-1.-1.mca").touch()
    header = b"\0\0\2\1" + bytes(8192 - 4)
    (folder / "r.0.0.mca").write_bytes(header + len(payload).to_bytes(4, "big") + payload)
    evidence = {"events": [{"player": [0, 0, 0, 1], "tick": 20, "captured_tick": 21,
                            "children": [[1, 2, 3, 4]]}], "alive": saved_alive_sheep(tmp_path)}
    assert surviving_offspring(evidence, UUID(int=1), 10, 30) == expected
