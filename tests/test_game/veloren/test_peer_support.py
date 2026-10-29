"""Safe opening healing and late healing cannot substitute for encounter support."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from game.team import create_team_binding
from game.veloren.evaluators.peer_support import support_checks
from tests.test_game.veloren.test_encounter import evidence


@pytest.mark.parametrize("count", [1, 3])
def test_native_group_rejects_unsupported_team_sizes_before_start(count):
    task = SimpleNamespace(
        game="veloren", tools=None, task_type="structured_tool",
        fixture={"peer_group": True}, participants=[None] * count,
    )
    with pytest.raises(ValueError, match="exactly two participants"):
        create_team_binding(task, Path("unused"), headless=True, recording=False, recording_fps=5)


def test_native_peer_heal_requires_original_enemy_hit_and_alive_window():
    first, last = evidence()
    initial, final = {}, {}
    for role, uid, entity in (("Alpha", 1, "player-generation-1"), ("Beta", 3, "peer-generation-1")):
        opening, closing = deepcopy(first), deepcopy(last)
        opening["self_identity"] = closing["self_identity"] = {"uid": uid}
        registry = {"run_id": "run", "nonce": "nonce", "opening_sequence": 10,
                    "identity": {"uid": uid}, "uid": uid, "server_entity": entity}
        for row, sequence in ((opening,10),(closing,20)):
            row["private_death_evidence"]={"schema":"livequest-player-deaths/1","registry":deepcopy(registry),
                                           "through_sequence":sequence,"events":[]}
        initial[role],final[role]=opening,closing
    damage=deepcopy(last["private_encounter_evidence"]["events"][0])
    damage.update(sequence=11)
    damage["data"].update(contributor={"Solo":2},contributor_entity="enemy-generation-1",
                          target_uid=1,target_entity="player-generation-1",server_time=5,
                          before=50,after=40,requested_amount=-10)
    heal=deepcopy(damage)
    heal.update(sequence=12)
    heal["data"].update(contributor={"Group":{"entity_uid":3,"group":7}},
                        contributor_entity="peer-generation-1",contributor_group=7,target_group=7,
                        cause={"Buff":"Regeneration"},before=40,after=42,requested_amount=2,server_time=20)
    lethal=deepcopy(last["private_encounter_evidence"]["events"][0]);lethal["sequence"]=13
    death=deepcopy(last["private_encounter_evidence"]["events"][1]);death["sequence"]=14
    final["Alpha"]["private_encounter_evidence"].update(events=[damage,heal,lethal,death],through_sequence=20)
    assert support_checks(initial,final,roles=["enemy"],window_seconds=30)["success"]
    for mutate in (
        lambda rows: rows[1]["data"].update(server_time=36),
        lambda rows: rows[0]["data"].update(contributor={"Solo":99}),
        lambda rows: rows[1]["data"].update(contributor={"Group":{"entity_uid":1,"group":7}},
                                            contributor_entity="player-generation-1"),
        lambda rows: rows[1]["data"].update(target_group=8),
    ):
        changed=deepcopy(final)
        mutate(changed["Alpha"]["private_encounter_evidence"]["events"])
        assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
        changed=deepcopy(final)
        rows=changed["Alpha"]["private_encounter_evidence"]["events"]
        rows[:]=[rows[0],rows[2],rows[1],rows[3]]
        for index,row in enumerate(rows):row["sequence"]=11+index
        assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
    changed=deepcopy(final)
    rows=changed["Alpha"]["private_encounter_evidence"]["events"]
    rows[:]=[rows[0],rows[2],rows[3],rows[1]]
    for index,row in enumerate(rows):row["sequence"]=11+index
    assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
