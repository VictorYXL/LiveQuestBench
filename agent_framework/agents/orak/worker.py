"""Adapt transport/configuration around Orak's unchanged native decision loop."""

import contextlib
import json
from pathlib import Path
import sys
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent_framework.utils.worker import WorkerBridge, WorkerStopped


def main() -> None:
    bridge = WorkerBridge()
    config = bridge.config
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))
    bridge.install_stop_handler()
    with contextlib.redirect_stdout(sys.stderr):
        from mcp_agent_client.base_agent import BaselineAgent
        from mcp_agent_client.runner.eval import BaseRunner

        # Orak loads game prompt modules by name. Supply only the injected public
        # instructions and the native memory fields, without Minecraft-specific advice.
        for name, template in {
            "action_inference_system": "{instructions}",
            "action_inference_user": "{task}\n{cur_state_str}\nPrevious action: {action}\nLast result: {last_result}",
        }.items():
            module = ModuleType(f"livequest_prompts.{name}")
            module.PROMPT = template
            sys.modules[module.__name__] = module

        class NativeAgent(BaselineAgent):
            def _setup_model(self):
                self.model_name = config["model"]

            def _setup_logger(self):
                pass

            def chat_completion(self, system_prompt, user_prompt, images=None, **kwargs):
                if images or kwargs:
                    raise ValueError("This Orak profile uses latest-image injection and no auxiliary model settings")
                response = bridge.rpc("chat", request={
                    "model": config["model"],
                    "reasoning_effort": config["reasoning_effort"],
                    "max_tokens": config["max_output_tokens"],
                    "messages": [{"role": "system", "content": system_prompt},
                                 {"role": "user", "content": user_prompt}],
                    "tools": [{"type": "function", "function": schema} for schema in config["tools"]],
                })
                message = response["choices"][0]["message"]
                calls = message.get("tool_calls", [])
                action = {"calls": [
                    {"name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"])}
                    for call in calls
                ]} if calls else {"final": message["content"]}
                return "### Actions\n" + json.dumps(action)

        class PublicObservation:
            def __init__(self):
                self.text = bridge.rpc("observe")

            def to_text(self):
                return self.text

        class GameTransport:
            finished = False
            answer = ""
            last_result = ""

            def initial_obs(self):
                return PublicObservation()

            def get_game_info(self):
                return {"instructions": config["instructions"], "task": config["task"],
                        "last_result": self.last_result}

            def text2action(self, text):
                return json.loads(text)

            def step(self, action):
                if set(action) == {"final"}:
                    if not isinstance(action["final"], str) or not action["final"].strip():
                        raise ValueError("Orak returned an empty final response")
                    self.answer, self.finished = action["final"], True
                elif set(action) == {"calls"} and action["calls"]:
                    results = [bridge.rpc("tool", name=call["name"], arguments=call["arguments"])
                               for call in action["calls"]]
                    self.last_result = json.dumps(results)
                else:
                    raise ValueError("Invalid native Orak action envelope")
                return PublicObservation(), None, self.finished, False, {}

            def evaluate(self, observation):
                return None, self.finished

        try:
            agent = NativeAgent({"llm_name": config["model"], "agent_type": "zeroshot_agent",
                                 "prompt_path": "livequest_prompts", "log_path": config["episode_id"]})
            environment = GameTransport()
            runner = BaseRunner({"max_steps": 1000})
            runner.set_agent(agent)
            runner.set_env(environment)
            bridge.rpc("ready", tools=[schema["name"] for schema in config["tools"]])
            _, steps = runner.play()
            Path("native_result.json").write_text(json.dumps({
                "steps": steps, "finished": environment.finished, "answer": environment.answer,
                "memory": agent.memory.memories,
            }, indent=2) + "\n")
            bridge.exit("returned" if environment.finished else "native_limit",
                        environment.answer, "BaseRunner.play/BaselineAgent.zeroshot")
        except WorkerStopped as error:
            bridge.exit("stopped", str(error), "benchmark_stop")


if __name__ == "__main__":
    main()
