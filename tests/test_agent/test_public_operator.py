import asyncio
import json
import time

import pytest

from agent_framework.agents.base_agent import AgentContext, AgentExitReason
from agent_framework.agents.public_operator import PublicOperator
from game.bindings import Controls


@pytest.mark.parametrize("malformed", [b'{"observation_index":', b"\xff"])
def test_operator_uses_only_scoped_pixels_and_frame_bound_motor_batches(tmp_path, malformed):
    async def scenario():
        calls = []

        async def observe():
            return [{"type": "image", "mime_type": "image/png", "data": b"Beta-only-pixels"}]

        async def execute(name, arguments):
            calls.append((name, arguments))
            return "accepted"

        now = time.monotonic_ns()
        context = AgentContext("peer.Beta", "public task", Controls(observe, execute),
                               now, now + 10_000_000_000, "only player Beta")
        output = tmp_path / "operator"
        agent = PublicOperator(output)
        running = asyncio.create_task(agent.run(context))

        async def wait_frame(index):
            async with asyncio.timeout(2):
                while not (output / "public/latest.json").exists() or json.loads(
                    (output / "public/latest.json").read_text()
                )["index"] != index:
                    await asyncio.sleep(.01)

        def publish(index, observation, request):
            pending = output / "commands" / f"{index:04d}.pending"
            pending.write_text(json.dumps({"observation_index": observation, "request": request}))
            pending.replace(pending.with_suffix(".json"))

        await wait_frame(0)
        assert (output / "public/0000.png").read_bytes() == b"Beta-only-pixels"
        action = {"commands": [{"name": "release_all", "arguments": {}}]}
        publish(1, 0, action)
        await wait_frame(1)
        publish(2, 0, action)
        await wait_frame(2)
        assert calls == [("action", action)]
        rejected = json.loads((output / "public/0002-action.json").read_text())
        assert rejected["response"]["executed_commands"] == 0
        pending = output / "commands/0003.pending"
        pending.write_bytes(malformed)
        pending.replace(pending.with_suffix(".json"))
        await wait_frame(3)
        assert calls == [("action", action)]
        assert json.loads((output / "public/0003-action.json").read_text())["response"]["error"] == (
            "invalid_request_json"
        )
        publish(4, 3, {"role": "Alpha", "tool": "CraftTool"})
        await wait_frame(4)
        assert calls == [("action", action)]
        assert json.loads((output / "public/0004-action.json").read_text())["response"]["error"] == (
            "ordinary_motor_batches_only"
        )
        publish(5, 4, {"observe": True})
        await wait_frame(5)
        assert calls == [("action", action)]
        publish(6, 5, {"finish": True})
        result = await asyncio.wait_for(running, 2)
        assert result.reason == AgentExitReason.COMPLETED
        receipt = json.loads((output / "public/0006-action.json").read_text())
        assert receipt["observation_index"] == 5
        assert receipt["request"]["request"] == {"finish": True}
        assert receipt["response"] == {
            "success": True, "operator_finished": True, "executed_commands": 0,
        }
        await agent.close()

    asyncio.run(scenario())
