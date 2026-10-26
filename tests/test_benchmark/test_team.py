"""Team configuration and peer isolation without live games or model calls."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from benchmark.config import ConfigError, load_task
from game.bindings import Controls, GameBinding
from game.team import TeamGame


def test_team_configuration_is_explicit_and_singleton_remains_default(tmp_path):
    path = Path("config/minecraft/tasks/structured_tools/reach_nearby_point.yaml")
    assert load_task(path).participants == ()
    assert "participants" not in load_task(path).resolved()
    data = yaml.safe_load(path.read_text())
    state = data["fixture"].pop("player_state")
    data["participants"] = [{"id": "Alpha", "player_state": state}, {"id": "Beta", "player_state": state}]
    data["evaluator"] = {"name": "team", "parameters": {"all": {"min_food": 0}}}
    target = tmp_path / "team.yaml"
    target.write_text(yaml.safe_dump(data))
    assert [role.id for role in load_task(target).participants] == ["Alpha", "Beta"]
    data["participants"][1]["id"] = "alpha"
    target.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigError, match="unique"):
        load_task(target)


def test_peer_chat_uses_only_receivers_own_native_connection(tmp_path):
    async def scenario():
        members, requests = {}, {}
        for role in ("Alpha", "Beta"):
            request = AsyncMock(return_value={"messages": [{"text": role + " private inbox"}]})
            requests[role] = request
            game = SimpleNamespace(
                _io=asyncio.Lock(), _check_running=lambda request=request: SimpleNamespace(bridge=SimpleNamespace(request=request)),
            )
            public = Controls(AsyncMock(return_value='{"position": [0, 0, 0]}'), AsyncMock(return_value="{}"))
            members[role] = GameBinding(game, lambda public=public: (public, []), None, None)
        team = TeamGame(SimpleNamespace(game="minecraft", task_type="structured_tool", tools=None), members, tmp_path)
        alpha, tools = team.controls("Alpha")
        beta, _ = team.controls("Beta")
        assert "Alpha private inbox" in await alpha.observe()
        assert "Beta private inbox" in await beta.observe()
        assert {tool.name for tool in tools} == {"BroadcastTool", "ChatTool"}
        await alpha.execute("ChatTool", {"recipient": "Beta", "message": "meet here"})
        requests["Alpha"].assert_awaited_with("chat_send", {"recipient": "Beta", "message": "meet here"})
        calls = requests["Alpha"].await_count
        for args in ({"recipient": "Admin", "message": "bad"}, {"recipient": "Beta", "message": "/op Alpha"},
                     {"recipient": "Beta", "message": "hello\n/op Alpha"}):
            assert '"executed": false' in await alpha.execute("ChatTool", args)
        assert requests["Alpha"].await_count == calls

    asyncio.run(scenario())


def test_peer_loops_share_deadline_and_preserve_early_member_exit(tmp_path, monkeypatch):
    from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason
    from benchmark.config import AgentConfig, ModelConfig
    from benchmark.results import EpisodeLog
    from benchmark.runner import run_bounded
    from benchmark.team import TeamAgent
    import benchmark.team as implementation
    import time

    async def scenario():
        early = asyncio.Event()
        late_continued = asyncio.Event()
        gate_closed = asyncio.Event()
        clients, agents, contexts = [], [], []

        class Peer:
            def __init__(self, first):
                self.first = first

            async def run(self, context):
                contexts.append(context)
                if self.first:
                    early.set()
                    return AgentExit(AgentExitReason.COMPLETED)
                await early.wait()
                late_continued.set()
                await asyncio.Event().wait()

            async def stop(self, reason):
                assert gate_closed.is_set()

            async def close(self):
                pass

        def make_client(*args):
            client = SimpleNamespace(close=AsyncMock())
            clients.append(client)
            return client

        def make_agent(*args):
            agent = Peer(not agents)
            agents.append(agent)
            return agent

        monkeypatch.setattr(implementation, "make_client", make_client)
        monkeypatch.setattr(implementation, "make_agent", make_agent)
        controls = Controls(AsyncMock(return_value="{}"), AsyncMock(return_value="{}"))
        game = SimpleNamespace(
            members={"Alpha": None, "Beta": None}, finish=AsyncMock(),
            controls=lambda role: (controls, []), instructions=lambda role: role,
        )
        team = TeamAgent(AgentConfig("baseline", "tool_calling", ModelConfig("github_copilot", "model")),
                         game, tmp_path, EpisodeLog(tmp_path, record_chat=False), record_chat=False)
        now = time.monotonic_ns()
        context = AgentContext("team", "Common goal", controls, now, now + 100_000_000)

        async def end():
            gate_closed.set()

        _, timed_out = await run_bounded(team, context, end)
        await team.close()
        assert timed_out and late_continued.is_set()
        assert len(clients) == len(agents) == 2 and clients[0] is not clients[1]
        assert contexts[0].deadline_at_ns == contexts[1].deadline_at_ns == context.deadline_at_ns
        assert team.results["Alpha"]["agent_exit"]["reason"] == "completed"
        assert all(task.done() for task in team.tasks)
        assert {call.args[0] for call in game.finish.await_args_list} == {"Alpha", "Beta"}

    asyncio.run(scenario())


def test_finishing_one_participant_does_not_end_shared_world(tmp_path):
    async def scenario():
        alpha, beta = SimpleNamespace(end=AsyncMock()), SimpleNamespace(end=AsyncMock())
        members = {"Alpha": SimpleNamespace(game=alpha), "Beta": SimpleNamespace(game=beta)}
        team = TeamGame(SimpleNamespace(game="veloren"), members, tmp_path)
        team.phase = "running"
        await team.finish("Alpha")
        alpha.end.assert_awaited_once()
        beta.end.assert_not_awaited()
        assert team.phase == "running"

    asyncio.run(scenario())


def test_team_goal_composition_uses_each_native_players_inventory(tmp_path, monkeypatch):
    from dataclasses import replace
    from uuid import uuid4
    from benchmark.config import ParticipantConfig
    from game.minecraft.init_player_state import PlayerState
    from game.team import create_team_binding

    task = load_task(Path("config/minecraft/tasks/structured_tools/reach_nearby_point.yaml"))
    state = dict(task.fixture["player_state"])
    state["inventory"] = [{"item": "minecraft:apple", "count": 1, "slot": 0}]
    task = replace(task, fixture={key: value for key, value in task.fixture.items() if key != "player_state"},
                   participants=(ParticipantConfig("Alpha", state), ParticipantConfig("Beta", {**state, "food": 5})),
                   evaluator="team", evaluator_parameters={
                       "all": {"min_food": 2}, "any": {"min_food": 10},
                       "roles": {"Alpha": {"inventory": [{"item": "apple", "min_count": 1}]}},
                       "inventory_total": [{"item": "apple", "min_count": 2}],
                   })
    games = []

    def member(config, *args, **kwargs):
        game = SimpleNamespace(player_uuid=uuid4(), player_state=PlayerState.from_dict(config.fixture["player_state"]))
        games.append(game)
        return GameBinding(game, None, None, None)

    monkeypatch.setattr("benchmark.factory.make_game", member)
    binding = create_team_binding(task, tmp_path / "game", headless=True, recording=False, recording_fps=10)
    for role, game in zip(("Alpha", "Beta"), games):
        for boundary in ("before", "after"):
            path = tmp_path / boundary / role
            path.mkdir(parents=True)
            game.player_state.write(path, game.player_uuid)
    score = binding.evaluate(tmp_path / "before", tmp_path / "after")
    assert score["success"]
    assert [check["scope"] for check in score["checks"]] == ["all", "any", "role", "inventory_total"]
    assert score["checks"][-1]["counts"] == {"Alpha": 1, "Beta": 1}
    games[0].player_state.inventory.clear()
    games[0].player_state.write(tmp_path / "after/Alpha", games[0].player_uuid, replace=True)
    score = binding.evaluate(tmp_path / "before", tmp_path / "after")
    assert not score["success"]
    assert not score["checks"][2]["passed"] and not score["checks"][3]["passed"]


def test_team_end_waits_for_an_already_ending_member(tmp_path):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        alpha = SimpleNamespace(phase="ending", _stopped=asyncio.Event())
        beta = SimpleNamespace(phase="running", _stopped=asyncio.Event(), end=AsyncMock())

        async def finish():
            assert alpha._stopped.is_set() and beta._stopped.is_set()
            entered.set()
            await release.wait()
            alpha.phase = "ended"

        alpha.end = finish
        game = TeamGame(SimpleNamespace(game="veloren"),
                        {"Alpha": SimpleNamespace(game=alpha), "Beta": SimpleNamespace(game=beta)}, tmp_path)
        game.phase = "running"
        ending = asyncio.create_task(game.end())
        await asyncio.wait_for(entered.wait(), 1)
        assert not ending.done()
        release.set()
        await ending
        assert game.phase == "ended"

    asyncio.run(scenario())
