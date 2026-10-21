"""Worker using Hermes' native conversation loop and public plugin interfaces."""

import contextlib
import json
import os
from pathlib import Path
import signal
import sys
import threading


def main() -> None:
    os.environ["HERMES_HOME"] = os.environ["HOME"]
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root))
    output = sys.stdout
    config = json.loads(sys.stdin.readline())
    lock = threading.Lock()
    sequence = 0

    def rpc(operation: str, **payload: object) -> object:
        nonlocal sequence
        with lock:
            sequence += 1
            output.write(json.dumps({"id": sequence, "op": operation, **payload}) + "\n")
            output.flush()
            reply = json.loads(sys.stdin.readline())
            if reply.get("id") != sequence:
                raise RuntimeError("Mismatched benchmark bridge reply")
            return reply["result"]

    with contextlib.redirect_stdout(sys.stderr):
        from openai.types.chat import ChatCompletion
        from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
        from run_agent import AIAgent
        from toolsets import TOOLSETS

        plugin = PluginContext(PluginManifest(name="livequestbench"), get_plugin_manager())
        names = [schema["name"] for schema in config["tools"]]
        TOOLSETS["livequestbench"] = {"description": "Restricted game tools", "tools": names, "includes": []}
        for schema in config["tools"]:
            def handle(arguments: dict, tool_name: str = schema["name"], **kwargs: object) -> str:
                result = rpc("tool", name=tool_name, arguments=arguments)
                if not isinstance(result, str):
                    raise TypeError("Game tool must return text")
                return result
            registration = plugin.register_tool(schema["name"], "livequestbench", schema, handle)
            if registration is None:
                raise RuntimeError(f"Could not register {schema['name']}")

        def model_call(request: dict, **kwargs: object) -> ChatCompletion:
            return ChatCompletion.model_validate(rpc("chat", request=request))

        plugin.register_middleware("llm_execution", model_call)
        agent = AIAgent(
            model=config["model"], base_url="http://127.0.0.1:9/v1", api_key="unused-local-bridge",
            provider="custom", api_mode="chat_completions", enabled_toolsets=["livequestbench"],
            max_tokens=config["max_output_tokens"],
            reasoning_config={"enabled": True, "effort": config["reasoning_effort"]},
            ephemeral_system_prompt=config["instructions"],
            skip_context_files=True, skip_memory=True, skip_background_review=True,
            quiet_mode=True, session_id=config["episode_id"], cwd=str(Path.cwd()),
        )
        signal.signal(signal.SIGTERM, lambda *_: agent.interrupt())
        try:
            rpc("ready", tools=sorted(agent.valid_tool_names))
            result = agent.run_conversation(config["task"])
            Path("native_result.json").write_text(json.dumps(result, default=str, indent=2) + "\n")
            if result.get("error") or result.get("interrupted"):
                raise RuntimeError(f"Hermes run failed: {result.get('error') or 'interrupted'}")
            answer = result.get("final_response")
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("Hermes returned no final response")
        finally:
            agent.close()
        output.write(json.dumps({"op": "exit", "result": {
            "reason": "returned", "message": answer, "native_reason": "run_conversation",
        }}) + "\n")
        output.flush()


if __name__ == "__main__":
    main()
