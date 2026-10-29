import asyncio

import pytest

from game.minecraft.evaluators.function_replication import truth_table_passes, probe_final, select_world


def cases():
    return [{"a": a, "b": b, "outputs": [int(a and b)]*3,
             "settled_outputs": [int(a and b)]*3}
            for a, b in ((0,0),(1,0),(1,1),(0,1))]


def test_final_truth_table_does_not_depend_on_exploration_attempts():
    and_outputs = {(a,b): int(a and b) for a,b in ((0,0),(1,0),(1,1),(0,1))}
    or_outputs = {(a,b): int(a or b) for a,b in and_outputs}
    assert truth_table_passes(cases(), and_outputs)
    assert not truth_table_passes(cases()[:-1], and_outputs)
    assert not truth_table_passes(cases(), or_outputs)
    changed = cases()
    changed[2]["outputs"][1] = 0
    assert not truth_table_passes(changed, and_outputs)
    unstable = cases()
    unstable[2]["settled_outputs"][2] = 0
    assert not truth_table_passes(unstable, and_outputs)


def test_frozen_distribution_selects_both_actual_native_functions(monkeypatch):
    from pathlib import Path
    from game.minecraft.evaluators.function_replication import initial_function, reference_table
    root = Path(__file__).resolve().parents[1] / "config/minecraft/fixtures/modular_build_procedure_transfer"
    selected = []
    for index in (0, 1):
        monkeypatch.setattr("secrets.randbelow", lambda n, index=index: index)
        world, receipt = select_world(root)
        selected.append(initial_function(world))
        assert receipt["instance_index"] == index
        assert reference_table(world)[(1, 0)] == index
    assert selected == ["AND", "OR"]


def test_hidden_family_cannot_silently_degrade_to_one_fixed_function(monkeypatch):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "config/minecraft/fixtures"
    with pytest.raises(ValueError, match="distribution manifest"):
        select_world(root / "modular_build_procedure_transfer_variant_b")
    monkeypatch.setattr("game.minecraft.evaluators.function_replication.initial_function",
                        lambda world: "AND")
    with pytest.raises(ValueError, match="distinct verified"):
        select_world(root / "modular_build_procedure_transfer")


def test_private_counterfactual_cannot_run_during_play():
    class Active:
        phase = "active"
    with pytest.raises(RuntimeError, match="closed episode"):
        asyncio.run(probe_final(Active(), None, None))
