"""Use smolagents' ToolCallingAgent.run with public model and Tool extensions."""

import contextlib
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent_framework.utils.worker import WorkerBridge, WorkerStopped


def main() -> None:
    bridge = WorkerBridge()
    config = bridge.config
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))
    bridge.install_stop_handler()
    with contextlib.redirect_stdout(sys.stderr):
        from smolagents import Model, Tool, ToolCallingAgent
        from smolagents.models import ChatMessage, REMOVE_PARAMETER
        from smolagents.monitoring import TokenUsage

        schemas = {schema["name"]: schema for schema in config["tools"]}

        class BridgeTool(Tool):
            output_type = "string"
            skip_forward_signature_validation = True

            def __init__(self, schema):
                self.name, self.description = schema["name"], schema["description"]
                self.inputs = deepcopy(schema["parameters"]["properties"])
                required = schema["parameters"].get("required", [])
                for name, field in self.inputs.items():
                    field.setdefault("description", name)
                    if name not in required:
                        field["nullable"] = True
                super().__init__()

            def forward(self, **arguments):
                return bridge.rpc("tool", name=self.name, arguments=arguments)

        class BridgeModel(Model):
            def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
                request = self._prepare_completion_kwargs(
                    messages, stop_sequences=stop_sequences, response_format=response_format,
                    tools_to_call_from=tools_to_call_from, flatten_messages_as_text=True, **kwargs,
                )
                if tools_to_call_from and {tool.name for tool in tools_to_call_from} != set(schemas):
                    raise ValueError("Native smolagents tool set changed")
                request["tools"] = [{"type": "function", "function": schema} for schema in schemas.values()]
                if not tools_to_call_from:
                    request["tool_choice"] = "none"
                response = bridge.rpc("chat", request={"model": config["model"], **request})
                usage = response.get("usage")
                return ChatMessage.from_dict(
                    response["choices"][0]["message"], raw=response,
                    token_usage=TokenUsage(usage["prompt_tokens"], usage["completion_tokens"]) if usage else None,
                )

        try:
            model = BridgeModel(
                model_id=config["model"], stop=REMOVE_PARAMETER,
                max_tokens=config["max_output_tokens"], reasoning_effort=config["reasoning_effort"],
            )
            agent = ToolCallingAgent(
                model=model, tools=[BridgeTool(schema) for schema in schemas.values()],
                instructions=config["instructions"], max_steps=1000, max_tool_threads=1,
                planning_interval=None, add_base_tools=False, verbosity_level=0,
            )
            bridge.rpc("ready", tools=sorted(agent.tools))
            answer = agent.run(config["task"])
            Path("native_result.json").write_text(json.dumps({
                "answer": str(answer), "steps": agent.step_number,
                "memory": agent.memory.get_full_steps(),
            }, default=str, indent=2) + "\n")
            bridge.exit("native_limit" if agent.step_number > agent.max_steps else "returned",
                        str(answer), "ToolCallingAgent.run")
        except WorkerStopped as error:
            bridge.exit("stopped", str(error), "benchmark_stop")


if __name__ == "__main__":
    main()
