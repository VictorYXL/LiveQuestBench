"""Offline recovery admission and private native death-evidence contracts."""

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
from uuid import UUID, uuid4

import pytest

pytest.importorskip("nbtlib", reason="Install the minecraft extra")
pytest.importorskip("Xlib", reason="Install the minecraft extra")
pytest.importorskip("PIL", reason="Install the minecraft extra")

from benchmark.config import load_task
from game.minecraft.binding import create_binding
from game.minecraft.evaluators.deaths import evaluate_deaths
from game.minecraft.structured_tools import interface as st


@pytest.fixture
def evidence_root():
    root = Path("output/test") / f"minecraft-recovery-{uuid4().hex}"
    root.mkdir(parents=True)
    for name, phase, tick in (("before", "ready", 1), ("after", "ended", 3)):
        world = root / name
        world.mkdir()
        (world / "_livequest_snapshot.json").write_text(json.dumps({
            "phase": phase, "player_uuid": str(UUID(int=1)), "sha256": {},
            "capture_started_at_ns": tick, "copied_at_ns": tick + 1,
        }))
    try:
        yield root
    finally:
        shutil.rmtree(root)


def write_deaths(world, count):
    (world / "stats").mkdir(parents=True, exist_ok=True)
    path = world / "stats" / f"{UUID(int=1)}.json"
    path.write_text(json.dumps({
        "DataVersion": 3700, "stats": {"minecraft:custom": {"minecraft:deaths": count}},
    }))
    manifest = world / "_livequest_snapshot.json"
    metadata = json.loads(manifest.read_text())
    metadata["sha256"][str(path.relative_to(world))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata))


def test_deaths_use_native_delta_not_respawn_attempts(evidence_root):
    before, after = evidence_root / "before", evidence_root / "after"
    assert evaluate_deaths(before, after, UUID(int=1))["deaths"]["count"] == 0
    write_deaths(after, 1)
    assert evaluate_deaths(before, after, UUID(int=1))["deaths"]["count"] == 1
    write_deaths(before, 4)
    write_deaths(after, 6)
    assert evaluate_deaths(before, after, UUID(int=1)) == {"deaths": {
        "count": 2, "before_count": 4, "after_count": 6,
        "source": "minecraft:custom/minecraft:deaths",
        "semantics": "native_player_deaths_during_episode",
        "player_uuid": str(UUID(int=1)),
    }}
    write_deaths(before, 7)
    with pytest.raises(ValueError, match="backwards"):
        evaluate_deaths(before, after, UUID(int=1))
    with pytest.raises(ValueError, match="phase"):
        evaluate_deaths(after, before, UUID(int=1))


@pytest.mark.parametrize("change", ["missing", "corrupt", "unlisted", "wrong_player", "missing_snapshot"])
def test_missing_or_changed_death_evidence_is_not_zero(evidence_root, change):
    before, after = evidence_root / "before", evidence_root / "after"
    write_deaths(after, 1)
    statistics = after / "stats" / f"{UUID(int=1)}.json"
    manifest = after / "_livequest_snapshot.json"
    metadata = json.loads(manifest.read_text())
    if change == "missing":
        statistics.unlink()
    elif change == "corrupt":
        statistics.write_text("{}")
    elif change == "unlisted":
        metadata["sha256"] = {}
        manifest.write_text(json.dumps(metadata))
    elif change == "wrong_player":
        metadata["player_uuid"] = str(UUID(int=2))
        manifest.write_text(json.dumps(metadata))
    else:
        manifest.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        evaluate_deaths(before, after, UUID(int=1))


@pytest.mark.parametrize("count", [-1, True, 1.5, "1", None])
def test_malformed_death_counts_rejected(evidence_root, count):
    write_deaths(evidence_root / "after", count)
    with pytest.raises(ValueError, match="Invalid native custom statistics"):
        evaluate_deaths(evidence_root / "before", evidence_root / "after", UUID(int=1))


@pytest.mark.parametrize("alive", [False, True])
def test_respawn_dispatch_preserves_native_confirmation(alive):
    calls = []
    result = {"success": not alive, "payload": (
        {"respawned": True, "health": 20} if not alive else {"failure_kind": "action_refused"}
    )}

    class Bridge:
        async def request(self, method, params, *, timeout):
            calls.append((method, params, timeout))
            await asyncio.sleep(0)
            return result

    assert asyncio.run(st.execute_tool(Bridge(), "RespawnTool", {})) == result
    assert calls == [("action", {
        "name": "respawn", "loop": "open_loop", "parameters": {},
    }, 60)]
    with pytest.raises(ValueError, match="Invalid arguments"):
        st.validate_tool("RespawnTool", {"restore_items": True})


def binding(evidence_root, tools):
    task = load_task(Path("tests/fixtures/legacy/config/minecraft/tasks/structured_tools/collect_logs.yaml"))
    return create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=tools, output_dir=evidence_root / "run",
        headless=True, recording=False, recording_fps=10,
    )


@pytest.mark.parametrize("allowed", [None, ("SelectTool",), ("SelectTool", "RespawnTool")])
def test_binding_admits_standard_recovery_and_private_metrics(evidence_root, monkeypatch, allowed):
    bound = binding(evidence_root, allowed)
    calls = []

    async def execute(name, args):
        calls.append((name, args))
        return {"success": True, "payload": {"respawned": True}}

    interface = st.StructuredInterface(None, execute, st.tool_schemas)
    monkeypatch.setattr(bound.game, "get_agent_interface", lambda: interface)
    controls, tools = bound.controls()
    names = [tool.name for tool in tools]
    assert names.count("RespawnTool") == 1
    if allowed is not None:
        assert set(names) == {*allowed, "RespawnTool"}
    asyncio.run(controls.execute("RespawnTool", {}))
    assert calls == [("RespawnTool", {})]
    assert not hasattr(controls, "metrics")
    bound.game.player_uuid = UUID(int=1)
    write_deaths(evidence_root / "after", 2)
    assert bound.metrics(evidence_root / "before", evidence_root / "after")["deaths"]["count"] == 2


@pytest.mark.parametrize("allowed", [
    (), ("SelectTool", "SelectTool"), ("RespawnTool", "RespawnTool"), ("UnknownTool",),
])
def test_original_allowlist_validated_before_recovery_admission(evidence_root, allowed):
    with pytest.raises(ValueError, match="allowlists|Unknown tools"):
        binding(evidence_root, allowed)
