import importlib.util
import io
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from PIL import ImageDraw
import pytest


SOURCE = Path(__file__).parents[2] / "fixtures/veloren/independent_motor_reference.py"
spec = importlib.util.spec_from_file_location("independent_motor_reference", SOURCE)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def image_bytes(value):
    output = io.BytesIO()
    Image.new("RGB", (960, 540), value).save(output, format="PNG")
    return output.getvalue()


def test_blank_frames_never_fabricate_native_trade():
    for color in ("black", "white"):
        for title in reference.TITLES:
            assert not reference.title_visible(image_bytes(color), title)


def test_declined_trade_does_not_advance_transfer(monkeypatch):
    visible = set()
    monkeypatch.setattr(reference, "title_visible", lambda png, title: title in visible)
    peer = reference.WorkshopPeer()
    visible.add("trade")
    assert peer.decide(b"own pixels")[0] == "offer"
    assert peer.decide(b"own pixels")[0] == "consent"
    visible.clear()
    assert peer.decide(b"own pixels")[0] == "wait_invitation"
    assert peer.transfer == 0
    visible.update(("trade", "review"))
    assert peer.decide(b"own pixels")[0] == "offer"
    visible.clear()
    assert peer.decide(b"own pixels")[0] == "sent_hides"
    assert peer.transfer == 1
    visible.update(("trade", "review"))
    assert peer.decide(b"own pixels")[0] == "consent"
    visible.clear()
    assert peer.decide(b"own pixels")[0] == "equip"


def test_chat_is_spaced_and_every_batch_preserves_native_wait_limit():
    batches = list(reference.chat_batches("at arch trade hides then bring boots"))
    assert len(batches) > 2
    for batch in batches:
        reference.validate_batch(batch)
    with pytest.raises(ValueError, match="unchanged public motor limit"):
        reference.validate_batch([reference.wait(10001)])
    with pytest.raises(ValueError, match="ordinary lowercase"):
        list(reference.chat_batches("/give item"))


def test_route_metric_failure_preserves_private_endpoint_diagnosis(tmp_path, monkeypatch):
    task = SimpleNamespace(
        task_type="visual_motor", participants=[SimpleNamespace(id=role) for role in ("Alpha", "Beta")],
        id="shared_workshop_exchange", task="public goal", time_limit_seconds=10,
        source=SimpleNamespace(sha256="task"), resolved=lambda: {"id": "shared_workshop_exchange"},
    )
    scoped = {role: object() for role in ("Alpha", "Beta")}
    game = SimpleNamespace(phase="new", instructions=lambda role: "only " + role,
                           controls=lambda role: (scoped[role], []))

    async def start():
        game.phase = "ready"

    async def begin():
        game.phase = "running"

    async def end():
        game.phase = "ended"

    async def close():
        game.phase = "closed"

    async def snapshot(path):
        assert game.phase in ("ready", "ended")
        return path

    game.start, game.begin, game.end, game.close = start, begin, end, close
    game.save_snapshot = snapshot

    def failed_route_metrics(before, after):
        assert game.phase == "ended"
        raise ValueError("native route/2 unsupported")

    binding = SimpleNamespace(
        game=game, verify_initial=lambda path: None,
        evaluate=lambda before, after: {"success": True}, metrics=failed_route_metrics,
    )

    class OwnOperator:
        def __init__(self, path):
            pass

        async def run(self, context):
            assert context.interface is scoped["Alpha"]

        async def close(self):
            pass

    async def own_beta(controls, output, task_id):
        assert controls is scoped["Beta"]
        return {"status": "finished"}

    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}")
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(runtime))
    monkeypatch.setattr(reference, "load_task", lambda path: task)
    monkeypatch.setattr(reference, "make_game", lambda *args, **kwargs: binding)
    monkeypatch.setattr(reference, "PublicOperator", OwnOperator)
    monkeypatch.setattr(reference, "beta_peer", own_beta)
    result = asyncio.run(reference.run(tmp_path / "task.yaml", tmp_path / "episode", 10, 10))
    assert result["status"] == "error"
    assert result["measurement"] == "unavailable"
    assert result["evaluation"] == {"success": True}
    assert result["stage"] == "native_route_metrics"
    assert "task_outcome" not in result
    assert game.phase == "closed"
    assert json.loads((tmp_path / "episode/result.json").read_text()) == result


def test_workshop_peer_does_not_expire_before_shared_deadline(tmp_path):
    class DeadlineReached(Exception):
        pass

    waiting = 0

    async def observe():
        return [{"type": "image", "mime_type": "image/png", "data": image_bytes("black")}]

    async def execute(name, arguments):
        nonlocal waiting
        if any(c == reference.command("key_down", key="y") for c in arguments["commands"]):
            waiting += 1
            if waiting == 503:
                raise DeadlineReached
        return "[]"

    with pytest.raises(DeadlineReached):
        asyncio.run(reference.beta_peer(SimpleNamespace(observe=observe, execute=execute),
                                       tmp_path / "Beta", "shared_workshop_exchange"))
    assert waiting == 503


def test_support_waits_for_own_public_group_damage_before_casting(tmp_path):
    class StopObservation(Exception):
        pass

    image = Image.new("RGB", (960, 540), "black")
    ImageDraw.Draw(image).rectangle((7, 27, 55, 36), fill=(70, 140, 0))
    data = io.BytesIO()
    image.save(data, format="PNG")
    calls, observations = [], 0

    async def observe():
        nonlocal observations
        observations += 1
        if observations == 6:
            raise StopObservation
        return [{"type": "image", "mime_type": "image/png", "data": data.getvalue()}]

    async def execute(name, arguments):
        calls.append(arguments["commands"])
        return "[]"

    with pytest.raises(StopObservation):
        asyncio.run(reference.beta_peer(SimpleNamespace(observe=observe, execute=execute),
                                       tmp_path / "Beta", "sceptre_and_sword_team"))
    assert not any(c["name"] == "mouse_down" for batch in calls[1:] for c in batch)


def test_public_combat_bar_detector_excludes_group_and_ground_colors():
    image = Image.new("RGB", (960, 540), (215, 120, 70))
    draw = ImageDraw.Draw(image)
    draw.rectangle((7, 27, 55, 36), fill=(70, 140, 0))
    draw.rectangle((360, 499, 440, 504), fill=(225, 23, 70))
    data = io.BytesIO()
    image.save(data, format="PNG")
    assert reference.enemy_bar(data.getvalue()) is None
    initial = reference.group_health_pixels(data.getvalue())
    draw.rectangle((35, 27, 55, 36), fill="black")
    draw.rectangle((510, 250, 580, 255), fill=(225, 23, 70))
    data = io.BytesIO()
    image.save(data, format="PNG")
    assert reference.group_health_pixels(data.getvalue()) < initial - 5
    x, y = reference.enemy_bar(data.getvalue())
    assert 510 < x < 580 and 275 < y < 295
    assert reference.own_health_pixels(data.getvalue()) == 0
    draw.rectangle((361, 499, 480, 503), fill=(70, 140, 0))
    data = io.BytesIO()
    image.save(data, format="PNG")
    assert 0 < reference.own_health_pixels(data.getvalue()) < 160


def test_trade_releases_cursor_and_clears_combat_before_equipping(monkeypatch):
    visible = {"trade", "review"}
    monkeypatch.setattr(reference, "title_visible", lambda png, title: title in visible)
    peer = reference.WorkshopPeer()
    peer.transfer = 1
    _, commands = peer.decide(b"own pixels")
    assert commands[0] == reference.command("key_down", key="comma")
    visible.clear()
    event, commands = peer.decide(b"own pixels")
    assert event == "equip"
    reference.validate_batch(commands)
    inventory = commands.index(reference.command("key_down", key="i"))
    assert reference.command("mouse_up", button="left") in commands[:inventory]
    assert reference.command("mouse_up", button="right") in commands[:inventory]
    assert commands.index(reference.command("release_all")) < inventory


def test_support_binds_finite_stock_before_attempting_hotbar_recovery(tmp_path):
    class BindingObserved(Exception):
        pass

    calls = []

    async def observe():
        return [{"type": "image", "mime_type": "image/png", "data": image_bytes("black")}]

    async def execute(name, arguments):
        calls.append(arguments["commands"])
        raise BindingObserved

    with pytest.raises(BindingObserved):
        asyncio.run(reference.beta_peer(SimpleNamespace(observe=observe, execute=execute),
                                       tmp_path / "Beta", "sceptre_and_sword_team"))
    first = calls[0]
    assert first[0] == reference.command("key_down", key="i")
    assert reference.command("mouse_move_to", x=779, y=402) in first
    assert reference.command("mouse_up", button="left") in first
    reference.validate_batch(first)
