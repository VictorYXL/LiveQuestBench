from uuid import UUID

import pytest

from game.minecraft.evaluators.threat_targets import summarize_targets, target_diagnostics
from game.minecraft.fixtures.threat_targets import prepare_target_trace


def native_uuid(value):
    return [int.from_bytes(value.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]


ALPHA, BETA, ENEMY, OTHER = (UUID(int=value) for value in (1, 2, 3, 4))


def frame(tick, target=None, player=False):
    row = {"enemy": native_uuid(ENEMY), "target_is_player": int(player)}
    if target is not None:
        row["target"] = native_uuid(target)
    return {"tick": tick, "enemies": [row]}


def test_native_targets_separate_peers_infighting_and_absent_target():
    result = summarize_targets(
        [frame(5, ALPHA, True), frame(25, ALPHA, True), frame(45, BETA, True),
         frame(65, OTHER), frame(85)],
        {"Alpha": ALPHA, "Beta": BETA}, 5, 85,
    )
    assert result["enemy_target_sample_counts"] == {
        "participant:Alpha": 1, "participant:Beta": 1, "none": 1, "nonplayer": 1,
    }
    assert result["maximum_sample_gap_ticks"] == 20
    assert result["frames"] == 4


@pytest.mark.parametrize("frames", [
    [frame(25), frame(25)], [frame(45), frame(25)], [frame(101)],
    [frame(25, ALPHA)], [{"tick": 25, "enemies": frame(25)["enemies"] * 2}],
])
def test_invalid_target_clock_or_attribution_is_rejected(frames):
    with pytest.raises(ValueError):
        summarize_targets(frames, {"Alpha": ALPHA}, 5, 100)


def test_old_fixture_without_optional_observer_stays_available(tmp_path):
    assert target_diagnostics(tmp_path / "before", tmp_path / "after", {})["status"] == "unavailable"


def test_changed_native_observer_is_rejected_before_reading_samples(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for world in (before, after):
        prepare_target_trace(world)
    observer = after / "datapacks/livequest_targets/data/livequest_targets/functions/enemy.mcfunction"
    observer.write_text("")
    with pytest.raises(ValueError, match="datapack changed"):
        target_diagnostics(before, after, {})
