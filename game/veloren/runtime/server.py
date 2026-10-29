"""Owned native server with explicit world settings; reuses verified lifecycle helpers."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess

from scripts.rpg_benchmark import lifecycle
from scripts.rpg_benchmark.native import NativeConfig


@asynccontextmanager
async def fixture_server(output: Path, record: dict, native: NativeConfig, fixture: dict):
    native.require_inputs()
    assert native.assets is not None and native.server is not None and native.root is not None
    asset = Path(fixture["world_path"]).resolve()
    if not asset.is_file():
        raise FileNotFoundError(f"Required Veloren map file is missing: {asset}")
    record["world_fixture"] = {
        "configuration": fixture, "map_path": str(asset),
        "map_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
    }
    port, web_port = lifecycle.free_port(), lifecycle.free_port()
    while port == web_port or lifecycle.protected_ports().intersection((port, web_port)):
        port, web_port = lifecycle.free_port(), lifecycle.free_port()
    userdata = output / "userdata"
    settings = userdata / "server/server_config/settings.ron"
    settings.parent.mkdir(parents=True, exist_ok=False)
    hour, minute = map(int, fixture["time_of_day"].split(":"))
    settings.write_text(
        f'(gameserver_protocols:[Tcp(address:"127.0.0.1:{port}")],'
        f'query_address:None,auth_server_address:None,world_seed:{fixture["world_seed"]},'
        f'map_file:Some(Load({json.dumps(str(asset))})),'
        f'day_length:{float(fixture["day_length"])},world:(start_time:{float(hour * 3600 + minute * 60)}),'
        'calendar_mode:None,experimental_terrain_persistence:false,server_name:"LiveQuestBench",)\n'
    )
    cli = userdata / "server-cli/settings.ron"
    cli.parent.mkdir()
    cli.write_text(f'(web_address:"127.0.0.1:{web_port}")\n')
    environment = {
        **os.environ, "VELOREN_USERDATA": str(userdata), "VELOREN_ASSETS": str(native.assets),
        "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
    }
    environment.pop("VELOREN_PRIVATE_NATIVE_FIXTURE", None)
    environment.pop("VELOREN_PRIVATE_ORACLE_PATH", None)
    environment.pop("VELOREN_INITIAL_MESSAGE_PROTOCOL", None)
    protocol = fixture.get("message_contract", {}).get("initialization_protocol")
    if protocol in ("initial-message-v2", "initial-message-v3"):
        environment["VELOREN_INITIAL_MESSAGE_PROTOCOL"] = protocol
    environment.update(
        VELOREN_PRIVATE_ORACLE_PATH=str(output / "private-native-oracle.ndjson"),
        VELOREN_SESSION_ID=output.name,
    )
    record["private_oracle"] = "Server-owner death/encounter/contract evidence; never public Agent input."
    provision = await asyncio.create_subprocess_exec(
        str(native.server), "--no-auth", "admin", "add", record["username"], "admin",
        cwd=native.root, env=environment, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, errors = await asyncio.wait_for(provision.communicate(), 30)
    finally:
        if provision.returncode is None:
            provision.kill()
            await provision.wait()
    if provision.returncode != 0:
        raise RuntimeError(f"Native administrator provisioning failed: {errors.decode(errors='replace')}")
    record.update(private_port=port, private_web_port=web_port, world_seed=fixture["world_seed"],
                  userdata=str(userdata), settings_sha256=hashlib.sha256(settings.read_bytes()).hexdigest())
    with (output / "server.log").open("xb") as log:
        process = subprocess.Popen(
            [str(native.server), "--no-auth", "--non-interactive"], cwd=native.root, env=environment,
            stdout=log, stderr=subprocess.STDOUT,
        )
        record.update(server_pid=process.pid, server_start_ticks=lifecycle.process_start_ticks(process.pid))
        try:
            record["private_listener_inode"] = await lifecycle.wait_for_server(process, port)
            expected = f"Assets found path={native.assets}"
            startup_log = (output / "server.log").read_text()
            if expected not in startup_log:
                raise RuntimeError("Server did not select the pinned assets directory")
            if any(message in startup_log for message in (
                "Couldn't read asset specifier for maps", "Couldn't parse modern map",
                "Couldn't read path for maps", "World size does not satisfy invariants",
                "Failed to parse setting file!", "Falling back to default settings",
            )):
                raise RuntimeError("Native fixture loading failed; fallback worlds/settings are not admitted")
            yield port, userdata
        finally:
            if process.poll() is None:
                lifecycle.assert_owned(process.pid, record["server_start_ticks"])
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait)
                    record["server_forced_termination"] = True
                    raise RuntimeError("Veloren server cleanup required forced termination")
            record.update(server_exit_code=process.returncode, server_stopped=process.returncode is not None)
