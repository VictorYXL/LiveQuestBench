"""Reference-only operator using one participant's public motor interface."""

import asyncio
import json
from pathlib import Path
import time

from agent_framework.agents.base_agent import AgentExit, AgentExitReason, BaseAgent


class PublicOperator(BaseAgent):
    """Consume numbered, atomically published requests bound to an observed frame."""

    def __init__(self, output: Path):
        self.output = output
        self.stopped = asyncio.Event()
        self.index = 0

    async def run(self, context):
        self.output.mkdir(parents=True, exist_ok=False)
        public, commands = self.output / "public", self.output / "commands"
        public.mkdir()
        commands.mkdir()
        (public / "instructions.txt").write_text(context.game_instructions + "\n" + context.task + "\n")

        async def capture():
            observation = await context.interface.observe()
            if not isinstance(observation, list):
                raise TypeError("The operator receives only native VM observations")
            images = [entry for entry in observation if entry["type"] == "image"]
            if len(images) != 1 or images[0]["mime_type"] != "image/png":
                raise ValueError("Expected one native PNG frame")
            (public / f"{self.index:04d}.png").write_bytes(images[0]["data"])
            (public / f"{self.index:04d}.json").write_text(json.dumps({
                "index": self.index,
                "elapsed_seconds": (time.monotonic_ns() - context.started_at_ns) / 1e9,
                "text": [entry["text"] for entry in observation if entry["type"] == "text"],
            }, indent=2) + "\n")
            latest = public / "latest.pending"
            latest.write_text(json.dumps({"index": self.index}) + "\n")
            latest.replace(public / "latest.json")

        await capture()
        while not self.stopped.is_set():
            request = commands / f"{self.index + 1:04d}.json"
            if not request.exists():
                await asyncio.sleep(.05)
                continue
            expected = self.index
            self.index += 1
            finished = False
            try:
                value = json.loads(request.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                value = None
                response = {"success": False, "error": "invalid_request_json",
                            "executed_commands": 0}
            else:
                if (not isinstance(value, dict) or set(value) != {"observation_index", "request"}
                        or type(value["observation_index"]) is not int
                        or value["observation_index"] != expected):
                    response = {"success": False, "error": "stale_or_invalid_observation_reference",
                                "executed_commands": 0}
                else:
                    action = value["request"]
                    if action == {"finish": True}:
                        finished = True
                        response = {"success": True, "operator_finished": True, "executed_commands": 0}
                    elif action == {"observe": True}:
                        response = None
                    elif isinstance(action, dict) and set(action) == {"commands"}:
                        response = await context.interface.execute("action", action)
                    else:
                        response = {"success": False, "error": "ordinary_motor_batches_only",
                                    "executed_commands": 0}
            (public / f"{self.index:04d}-action.json").write_text(json.dumps({
                "observation_index": expected, "request": value, "response": response,
            }, indent=2) + "\n")
            if finished:
                return AgentExit(AgentExitReason.COMPLETED, native_reason="operator_finished")
            await capture()
        return AgentExit(AgentExitReason.STOPPED, native_reason="benchmark_stop")

    async def stop(self, reason):
        self.stopped.set()

    async def close(self):
        self.stopped.set()
