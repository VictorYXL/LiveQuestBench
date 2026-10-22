"""Opt-in production-CLI admission, deadline and operating-system interrupt checks."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.live
@pytest.mark.game
@pytest.mark.parametrize("case", ["native", "deadline", "interrupt"])
def test_cli_lifecycle(case, headless, recording):
    if os.environ.get("LIVEQUEST_BENCHMARK_TEST") != "1" or os.environ.get("LIVEQUEST_LIVE_COPILOT") != "1":
        pytest.skip("Set LIVEQUEST_BENCHMARK_TEST=1 and LIVEQUEST_LIVE_COPILOT=1")
    root = ROOT / "output/test" / f"benchmark-{case}-{uuid4().hex}"
    root.mkdir(parents=True)
    task = yaml.safe_load((ROOT / "config/veloren/tasks/structured_tools/move_2_metres.yaml").read_text())
    task["fixture"]["world_path"] = str(
        (ROOT / "config/veloren/tasks/structured_tools" / task["fixture"]["world_path"]).resolve()
    )
    task["tools"] = ["MoveTool"]
    experiment = yaml.safe_load((ROOT / "config/veloren/experiments/visual_motor_all.yaml").read_text())
    experiment["tasks"] = [{"path": "task.yaml"}]
    experiment["repetitions"] = 1
    if case == "native":
        experiment["agents"][0]["name"] = "deepseek_harness"
    else:
        task["task"] = (
            "Keep taking short movement bursts until the benchmark stops you. "
            "Do not finish early. Stay alive; alternate forward and backward movement."
        )
        task["evaluator"]["parameters"]["min_distance"] = 1000
    if case == "deadline":
        task["time_limit_seconds"] = 3
    (root / "task.yaml").write_text(yaml.safe_dump(task))
    (root / "experiment.yaml").write_text(yaml.safe_dump(experiment))
    output = root / "run"
    command = [
        sys.executable, str(ROOT / "run_benchmark.py"), "--config", str(root / "experiment.yaml"),
        "--output", str(output), "--headless" if headless else "--no-headless",
        "--recording" if recording else "--no-recording",
    ]
    with (root / "cli.log").open("w") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            if case == "interrupt":
                limit = time.monotonic() + 180
                while time.monotonic() < limit and process.poll() is None:
                    traces = list(output.glob("*/*/episode_*/trace.jsonl"))
                    if traces and '"event": "observation"' in traces[0].read_text():
                        process.send_signal(signal.SIGINT)
                        break
                    time.sleep(0.05)
                else:
                    pytest.fail("CLI did not reach a live observation before interruption")
            code = process.wait(timeout=300)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                    pytest.fail(f"CLI required forced termination; evidence: {root}")
    summary = json.loads((output / "summary.json").read_text())
    assert code == (130 if case == "interrupt" else 0), (root / "cli.log").read_text()
    assert summary["status"] == ("cancelled" if case == "interrupt" else "completed")
    result = json.loads((output / summary["episodes"][0]["output_path"] / "result.json").read_text())
    assert result["accounting"]["request_attempts"] >= 1
    assert [tool["name"] for tool in result["tools"]] == ["MoveTool"]
    episode = output / result["output_path"]
    assert (episode / "before/observation.json").exists()
    assert (episode / "after/observation.json").exists()
    if case == "native":
        assert result["native_agent"] == {"admitted": True, "forced_termination": False}
        assert result["accounting"]["tool_calls"] >= 1
    elif case == "deadline":
        assert result["deadline_reached"] and result["agent_exit"]["reason"] == "stopped"
        assert result["task_outcome"] == "failure"
        assert result["measurement"] == "valid"
    else:
        assert result["status"] == "cancelled"
        assert not [error for error in result["errors"] if "cleanup" in error["stage"]]
