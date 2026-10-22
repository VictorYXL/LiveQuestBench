"""Bind the native GamingAgent harness and runner to public model/game transport."""

import argparse
import base64
import contextlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent_framework.utils.worker import WorkerBridge, WorkerStopped


def main() -> None:
    bridge = WorkerBridge()
    config = bridge.config
    root = Path(sys.argv[1]).resolve()
    sys.path[:0] = [str(root), str(root / "lmgame-bench")]
    bridge.install_stop_handler()
    with contextlib.redirect_stdout(sys.stderr):
        from gamingagent.agents.base_agent import BaseAgent
        from gamingagent.modules import CoreModule, Observation, PerceptionModule, ReasoningModule
        from single_agent_runner import run_game_episode

        class ModelTransport:
            def __init__(self, game_name, vllm_url=None, modal_url=None):
                if vllm_url or modal_url or game_name not in ("base", "perception", "memory", "reasoning"):
                    raise ValueError("Unsupported native model transport configuration")
                self.role = game_name

            def text_only_completion(
                self, *, model_name, system_prompt, prompt, thinking, reasoning_effort, token_limit,
                image_path=None,
            ):
                if (model_name, reasoning_effort, token_limit) != (
                    config["model"], config["reasoning_effort"], config["max_output_tokens"],
                ):
                    raise ValueError("Native module changed the experiment model configuration")
                content = prompt
                if image_path is not None:
                    content = [
                        {"type": "text", "text": prompt},
                        {"type": "image", "mime_type": "image/png",
                         "data": base64.b64encode(Path(image_path).read_bytes()).decode("ascii")},
                    ]
                response = bridge.rpc("chat", request={
                    "model": model_name, "reasoning_effort": reasoning_effort, "max_tokens": token_limit,
                    "messages": [{"role": "system", "content": system_prompt},
                                 {"role": "user", "content": content}],
                    "tools": [{"type": "function", "function": schema} for schema in config["tools"]],
                    "tool_choice": "auto" if self.role == "reasoning" else "none",
                })
                message = response["choices"][0]["message"]
                if self.role == "reasoning":
                    calls = message.get("tool_calls", [])
                    action = {"calls": [
                        {"name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"])}
                        for call in calls
                    ]} if calls else {"final": message["content"]}
                    result = json.dumps({"action": json.dumps(action), "thought": message["content"] or ""})
                else:
                    if message.get("tool_calls") or not isinstance(message["content"], str) or not message["content"].strip():
                        raise ValueError("Perception/reflection requires a nonempty text response without actions")
                    result = message["content"]
                return (result,)

            vision_text_completion = text_only_completion

        class FixedToolReasoning(ReasoningModule):
            def _parse_response(self, response):
                return json.loads(response)

        class GameTransport:
            preserve_action_case = True

            def __init__(self):
                self.finished = False
                self.answer = ""
                self.steps = 0
                self.captures = 0
                self.adapter = self
                self.initial = self.observe()
                self.mode = "both" if self.initial.img_path else "text"
                self.reset_used = False

            def observe(self, last_result=""):
                public = bridge.rpc("observe")
                image_path = None
                text_parts = [public] if isinstance(public, str) else []
                if isinstance(public, list):
                    for block in public:
                        if block["type"] == "text":
                            text_parts.append(block["text"])
                        elif block["type"] == "image":
                            if image_path is not None or block["mime_type"] != "image/png":
                                raise ValueError("GamingAgent expects one public PNG frame")
                            image_path = f"frame-{self.captures:04d}.png"
                            Path(image_path).write_bytes(base64.b64decode(block["data"], validate=True))
                        else:
                            raise ValueError("Unsupported public observation block")
                self.captures += 1
                return Observation(
                    img_path=image_path, textual_representation="\n".join(text_parts) + last_result,
                    background=config["task"], max_memory=20,
                )

            def reset(self, *, max_memory, seed, episode_id):
                if self.reset_used or max_memory != 20 or seed is not None:
                    raise ValueError("Only the benchmark may initialize an episode")
                self.reset_used = True
                return self.initial, {}

            def render(self):
                # Rendering is already continuous in the benchmark-owned client.
                pass

            def step(self, *, agent_action_str, thought_process, time_taken_s):
                action = json.loads(agent_action_str)
                self.steps += 1
                last_result = ""
                if set(action) == {"calls"} and action["calls"]:
                    results = [bridge.rpc("tool", name=call["name"], arguments=call["arguments"])
                               for call in action["calls"]]
                    last_result = "\nLast tool results: " + json.dumps(results)
                elif set(action) == {"final"} and isinstance(action["final"], str) and action["final"].strip():
                    self.finished, self.answer = True, action["final"]
                else:
                    raise ValueError("Invalid GamingAgent action envelope")
                observation = self.observe(last_result)
                self.latest = observation
                # Native runner arithmetic needs numbers; NaN explicitly means
                # unavailable, not a zero reward or a private benchmark score.
                return observation, float("nan"), self.finished, False, {"total_score": float("nan")}, float("nan")

            def record_episode_result(self, *, episode_id, score, steps, total_reward, total_perf_score):
                Path("native_result.json").write_text(json.dumps({
                    "steps": steps, "finished": self.finished, "answer": self.answer,
                    "native_scores": None, "score_status": "not_exposed",
                    "memory": self.latest.game_trajectory.get(),
                }, indent=2, allow_nan=False) + "\n")

        try:
            CoreModule.api_manager_factory = staticmethod(ModelTransport)
            bridge.rpc("ready", tools=[schema["name"] for schema in config["tools"]])
            environment = GameTransport()
            shared_system = config["instructions"] + "\nTask: " + config["task"]
            prompts = {
                "perception_module": {
                    "system_prompt": shared_system,
                    "prompt": "Describe the visible scene relevant to the task. Do not choose or execute actions.",
                },
                "memory_module": {"reflection": {
                    "system_prompt": shared_system,
                    "prompt": "Reflect on progress and consequences using the public observations.\n"
                              "Previous context:\n{prev_context}\nCurrent observation:\n{current_observation}",
                }},
                "reasoning_module": {
                    "system_prompt": shared_system,
                    "prompt": "Choose the next action using the supplied tools, or answer when finished.\n"
                              "Current observation: {textual_representation}\n"
                              "Visual description: {processed_visual_description}\n"
                              "History: {game_trajectory}\nReflection: {reflection}",
                },
            }
            Path("prompts.json").write_text(json.dumps(prompts, indent=2) + "\n")
            agent = BaseAgent(
                game_name="livequest", model_name=config["model"], config_path="prompts.json",
                harness=True, max_memory=20, use_reflection=True, use_perception=True, use_summary=False,
                cache_dir="native", observation_mode=environment.mode, token_limit=config["max_output_tokens"],
                custom_modules={"perception_module": PerceptionModule, "reasoning_module": FixedToolReasoning},
            )
            for module in agent.modules.values():
                if module is not None:
                    module.reasoning_effort = config["reasoning_effort"]
            run_game_episode(agent, environment, 0, argparse.Namespace(
                max_memory=20, seed=None, max_steps_per_episode=1000, game_name="livequest",
            ))
            bridge.exit("returned" if environment.finished else "native_limit",
                        environment.answer, "run_game_episode/BaseAgent.get_action/harness")
        except WorkerStopped as error:
            bridge.exit("stopped", str(error), "benchmark_stop")


if __name__ == "__main__":
    main()
