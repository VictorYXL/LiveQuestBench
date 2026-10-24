"""Single-experiment Minecraft lifecycle; administrative state never reaches Agent tools."""

import asyncio
from collections import deque
from configparser import ConfigParser
from contextlib import AsyncExitStack, nullcontext
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
from typing import BinaryIO
from uuid import UUID

import nbtlib
from Xlib import X, display

from game.backends.x11.actions import WindowActions
from game.backends.x11.capture import WindowCapture
from game.minecraft.runtime.install import (
    INSTANCE_ID, PRISM_APP_ID, check_instance, check_java, check_prism, data_root, prism_root, server_jar,
)
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.init_player_state import PlayerState
from game.minecraft.runtime.bridge import NativeBridge
from game.minecraft.runtime.client import check_client, launch_command


class CasePreservingConfig(ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and in [{low}, {high}]")
    return float(value)


def integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


@dataclass
class SessionConfig:
    player_name: str
    player_uuid: UUID
    display: str
    instance: str = INSTANCE_ID
    port: int = 0
    memory_mb: int = 2048
    startup_timeout: float = 120
    stop_timeout: float = 30
    difficulty: str = "normal"
    authentication: str = "offline"
    account: str | None = None
    track: str = "visual_motor"

    @classmethod
    def from_dict(cls, values: dict) -> "SessionConfig":
        if not isinstance(values, dict) or values.keys() - set(cls.__dataclass_fields__):
            raise ValueError(f"game config allows only {list(cls.__dataclass_fields__)}")
        name = values.get("player_name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,16}", name):
            raise ValueError("Resolved account must have a valid Minecraft profile name")
        raw_uuid = values.get("player_uuid")
        if not isinstance(raw_uuid, str):
            raise ValueError("Resolved account must have a Minecraft profile UUID")
        display_name = values.get("display", os.environ.get("DISPLAY", ""))
        if not isinstance(display_name, str) or not display_name:
            raise ValueError("An authorized X11 display is required; set runtime.display or DISPLAY")
        instance = values.get("instance", INSTANCE_ID)
        if not isinstance(instance, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", instance) or instance in {".", ".."}:
            raise ValueError("instance must be a Prism instance folder ID")
        difficulty = values.get("difficulty", "normal")
        if difficulty not in ("peaceful", "easy", "normal", "hard"):
            raise ValueError("difficulty must be peaceful, easy, normal, or hard")
        authentication = values.get("authentication", "offline")
        if authentication not in ("offline", "online"):
            raise ValueError("authentication must be offline or online")
        track = values.get("track", "visual_motor")
        if track not in ("visual_motor", "structured_tool"):
            raise ValueError("Unknown Minecraft track")
        if track == "structured_tool" and authentication != "offline":
            raise ValueError("ST currently supports local offline authentication only")
        return cls(
            player_name=name, player_uuid=UUID(raw_uuid), display=display_name, instance=instance,
            port=integer(values.get("port", 0), "port", 0, 65535),
            memory_mb=integer(values.get("memory_mb", 2048), "memory_mb", 512, 1048576),
            startup_timeout=number(values.get("startup_timeout", 120), "startup_timeout", 1, 3600),
            stop_timeout=number(values.get("stop_timeout", 30), "stop_timeout", 1, 300),
            difficulty=difficulty,
            authentication=authentication, account=values.get("account"),
            track=track,
        )


def validate_world(source: Path) -> None:
    """Require a self-contained, player-free native save; never generate missing worlds."""
    if source.is_symlink():
        raise ValueError("Source world cannot be a symlink")
    source = source.resolve(strict=True)
    if not (source / "level.dat").is_file():
        raise ValueError("world must point to the native save containing level.dat")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Source save contains symlinks; provide a self-contained offline snapshot")
    with WorldReadLock(source):
        data = nbtlib.load(source / "level.dat")["Data"]
        if int(data.get("DataVersion", 0)) != 3700:
            raise ValueError("Source world must be a Minecraft Java 1.20.4 save")
        if "Player" in data or any(
            path.is_file() for folder in ("playerdata", "advancements", "stats")
            for path in (source / folder).rglob("*")
        ):
            raise ValueError("Source world must not contain player data")


def copy_world(source: Path, destination: Path, state: PlayerState, player_uuid: UUID) -> None:
    """Copy an offline 1.20.4 save, never following symlinks or copying player data."""
    validate_world(source)
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Destination cannot be inside the source world")
    if destination.exists():
        raise FileExistsError(f"World destination must be new: {destination}")
    with WorldReadLock(source):
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("session.lock"))
    state.write(destination, player_uuid)


class WorldReadLock:
    """Use the same POSIX byte-range lock as Java without writing the source."""
    def __init__(self, source: Path):
        self.path = source / "session.lock"
        self.file = None

    def __enter__(self):
        if self.path.exists():
            self.file = self.path.open("rb")
            try:
                fcntl.lockf(self.file, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BaseException:
                self.file.close()
                raise
        return self

    def __exit__(self, *_args):
        if self.file is not None:
            self.file.close()


def prism_instances() -> list[str]:
    result = subprocess.run(
        ["flatpak", "ps", "--columns=instance,application"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return [fields[0] for line in result.stdout.splitlines()
            if len(fields := line.split()) == 2 and fields[1] == PRISM_APP_ID]


class MinecraftSession:
    def __init__(self, output: Path, config: SessionConfig, state: PlayerState, *, world: Path):
        self.output, self.config, self.state = output, config, state
        self.world = world.resolve()
        if self.world.parent != output.resolve() or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.world.name):
            raise ValueError("The running world must be a named directory directly inside output_dir")
        self.server: MinecraftServer | None = None
        self.capture: WindowCapture | None = None
        self.actions: WindowActions | None = None
        self.window_id: int | None = None
        self.bridge: NativeBridge | None = None
        self._client: asyncio.subprocess.Process | None = None
        self._flatpak_id: str | None = None
        self._client_errors: deque[str] = deque(maxlen=12)
        self._client_reader: asyncio.Task | None = None
        self._stack = AsyncExitStack()
        self._client_root: Path | None = None
        self._client_identity: BinaryIO | None = None
        self._java = ""
        self._jar = server_jar()

    def preflight(self) -> None:
        if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
            raise PermissionError("Review the Minecraft EULA and explicitly set MINECRAFT_EULA_ACCEPTED=true")
        self._java = check_java()
        if not self._jar.is_file():
            raise FileNotFoundError("Server jar missing; run game/minecraft/setup.sh first")
        (data_root() / "locks").mkdir(parents=True, exist_ok=True)
        if self.config.authentication == "online":
            check_prism()
            check_instance(self.config.instance)
        else:
            check_client()
        display_name = re.sub(r"\.\d+$", "", self.config.display)
        display_key = hashlib.sha256(display_name.encode()).hexdigest()
        lock = data_root() / "locks" / f"display-{display_key}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        display_lock = self._stack.enter_context(lock.open("a"))
        try:
            fcntl.flock(display_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another visual experiment owns this X11 display; use separate virtual displays") from exc
        with WindowCapture(self.config.display, title_prefix="Minecraft", class_tokens=("minecraft", "lwjgl")) as capture:
            if capture.list_windows():
                raise RuntimeError("The selected display already has a Minecraft window")
        self._prepare_client()

    def _prepare_client(self) -> None:
        if self.config.authentication == "offline":
            self._client_root = self.output / "client"
            return
        source = prism_root()
        # Keep credential copies outside run artifacts, inside a private app-data directory.
        directory = self._stack.enter_context(tempfile.TemporaryDirectory(
            prefix="livequestbench-", dir=source.parent,
        ))
        self._client_root = Path(directory)
        for name in ("accounts.json", "prismlauncher.cfg", "metacache"):
            with (source / name).open("rb") as original, (self._client_root / name).open("xb") as copied:
                os.fchmod(copied.fileno(), 0o600)
                shutil.copyfileobj(original, copied)
        settings = CasePreservingConfig(interpolation=None, delimiters=("=",))
        settings_path = self._client_root / "prismlauncher.cfg"
        with settings_path.open(encoding="utf-8") as stream:
            settings.read_file(stream)
        settings["General"].update({
            "InstanceDir": "instances", "CentralModsDir": "mods", "IconsDir": "icons",
            "JavaDir": "java", "CloseAfterLaunch": "false", "QuitAfterGameStop": "false",
        })
        with settings_path.open("w", encoding="utf-8") as stream:
            settings.write(stream, space_around_delimiters=False)
        for name in ("assets", "libraries", "java", "meta"):
            resource = source / name
            if not resource.is_dir():
                raise FileNotFoundError(f"Prism resource cache missing; launch the template instance once: {resource}")
        (self._client_root / "java").symlink_to(source / "java", target_is_directory=True)
        # Refreshed indexes may reference objects absent from an otherwise warm cache.
        for name in ("libraries", "meta", "assets"):
            shutil.copytree(source / name, self._client_root / name)
        instance = self._client_root / "instances" / self.config.instance
        shutil.copytree(
            source / "instances" / self.config.instance, instance,
            ignore=shutil.ignore_patterns("saves", "logs", "screenshots", "crash-reports"),
        )
        with (instance / "instance.cfg").open(encoding="utf-8") as stream:
            settings = CasePreservingConfig(interpolation=None, delimiters=("=",))
            settings.read_file(stream)
        settings["General"].update({"CloseAfterLaunch": "false", "QuitAfterGameStop": "false"})
        with (instance / "instance.cfg").open("w", encoding="utf-8") as stream:
            settings.write(stream, space_around_delimiters=False)
        self._client_identity = self._stack.enter_context(tempfile.TemporaryFile())

    def _reserve_port(self) -> int:
        for _ in range(32):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", self.config.port))
                port = probe.getsockname()[1]
                lock = (data_root() / "locks" / f"server-{port}.lock").open("a")
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lock.close()
                    if self.config.port:
                        raise RuntimeError(f"Another experiment has reserved server port {port}") from None
                    continue
                except BaseException:
                    lock.close()
                    raise
                self._stack.callback(lock.close)
                return port
        raise RuntimeError("Could not reserve an unused server port")

    def _prepare_server(self) -> int:
        port = self._reserve_port()
        properties = {
            "server-ip": "127.0.0.1", "server-port": str(port),
            "online-mode": str(self.config.authentication == "online").lower(),
            "enforce-secure-profile": str(self.config.authentication == "online").lower(),
            "enable-rcon": "false", "enable-query": "false", "level-name": self.world.name,
            "max-players": "1",
            "gamemode": self.state.gamemode, "force-gamemode": "false",
            "difficulty": self.config.difficulty, "spawn-protection": "0", "view-distance": "6",
            "simulation-distance": "6", "broadcast-console-to-ops": "false",
        }
        (self.output / "server.properties").write_text(
            "".join(f"{key}={value}\n" for key, value in properties.items()), encoding="utf-8",
        )
        (self.output / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        return port

    async def start(self) -> None:
        port = self._prepare_server()
        self.server = MinecraftServer(
            self.output, self._jar, self._java, self.config.memory_mb, port,
            self.config.startup_timeout, self.config.stop_timeout,
        )
        self._stack.push_async_callback(self.server.stop)
        await self.server.start()
        feedback = await self.server.command("tick freeze")
        if not any("The game is frozen" in line for line in feedback):
            raise RuntimeError("Could not verify freezing the experiment during initialization")
        self.capture = self._stack.enter_context(WindowCapture(
            self.config.display, title_prefix="Minecraft", class_tokens=("minecraft", "lwjgl"),
        ))
        self._stack.push_async_callback(self._stop_client)
        try:
            await self._start_client(port)
        except TimeoutError as exc:
            raise TimeoutError(
                "The client did not produce a connected Minecraft window before startup_timeout. "
                "Check client.log for native launch or the Prism instance for authenticated launch. "
                "No startup retry was performed.\n" + "\n".join(self._client_errors)
            ) from exc
        await self._verify_player()
        assert self.window_id is not None
        self.actions = self._stack.enter_context(WindowActions(
            self.window_id, self.config.display,
        ))
        if self.bridge is not None:
            async with asyncio.timeout(self.config.startup_timeout):
                while not (await self.bridge.request("ready", {}))["ready"]:
                    await asyncio.sleep(0.1)
        await self._verify_input_ready()
        await self._verify_player()
        if (self.world / "livequest-expedition.json").is_file():
            from game.minecraft.evaluators.expedition import registry
            from game.minecraft.fixtures.forge_hunt import targets_for, uuid_parts
            expected = registry(self.world)
            targets = expected.get("targets", targets_for())
            for enemy in targets + expected.get("merchants", []):
                target = UUID(enemy["uuid"])
                native_uuid = "[I;" + ",".join(map(str, uuid_parts(target))) + "]"
                lines = await self.server.command(
                    f"execute as @e[type={enemy['type']},nbt={{UUID:{native_uuid}}},limit=1] run data get entity @s"
                )
                values = [nbtlib.parse_nbt(line.split("has the following entity data: ", 1)[1])
                          for line in lines if "has the following entity data: " in line]
                if (len(values) != 1 or list(values[0]["UUID"]) != uuid_parts(target)
                        or float(values[0]["Health"]) != enemy["health"]):
                    raise RuntimeError(f"Expedition target missing, injured or changed: {enemy['role']}")
                if enemy in expected.get("merchants", []):
                    from game.minecraft.fixtures.trade_hunt import offers
                    actual = values[0]["Offers"]["Recipes"]
                    required = offers(enemy["role"])
                    if len(actual) != len(required) or any(
                        any(row[key] != value for key, value in wanted.items())
                        for row, wanted in zip(actual, required)
                    ):
                        raise RuntimeError("Initial native merchant stock or price differs from the fixture")
            opening = {"target_uuid": expected["target_uuid"], "health": targets[0]["health"],
                       "player_uuid": str(self.config.player_uuid)}
            if "targets" in expected:
                opening["targets"] = targets
            if "merchants" in expected:
                opening["merchants"] = expected["merchants"]
            if "route_gates" in expected:
                for gate in expected["route_gates"]:
                    for key, block in (("open_z", "air"), ("closed_z", "stone_bricks")):
                        for y in (72, 73):
                            lines = await self.server.command(
                                f"execute if block {gate['x']} {y} {gate[key]} minecraft:{block} "
                                "run data get storage livequest:expedition state"
                            )
                            if not any("has the following contents:" in line for line in lines):
                                raise RuntimeError("Reconnaissance passage differs from the declared condition")
                opening["route_gates"] = expected["route_gates"]
            (self.world / "livequest-opening.json").write_text(json.dumps(opening, indent=2) + "\n")

    async def _verify_input_ready(self) -> None:
        """Verify mouse/keyboard acceptance and restore the starting view and slot."""
        assert self.actions is not None and self.server is not None
        player_name = self.config.player_name
        async with asyncio.timeout(self.config.startup_timeout):
            # Minecraft discards its first cursor event after grabbing the mouse.
            while True:
                self.actions.mouse_move_relative(4, 0)
                await asyncio.sleep(0.15)
                data = await self.server.player_data(player_name)
                if data is not None:
                    yaw_change = (float(data["Rotation"][0]) - self.state.yaw + 180) % 360 - 180
                    if abs(yaw_change) > 0.01:
                        break
            feedback = await self.server.command(
                f"execute as {player_name} at @s run tp @s ~ ~ ~ "
                f"{self.state.yaw} {self.state.pitch}"
            )
            if not any("Teleported" in line for line in feedback):
                raise RuntimeError("Could not restore the initial view after mouse readiness verification")
            for key, slot in (("2", 1), ("1", 0)):
                while True:
                    self.actions.key_down(key)
                    try:
                        await asyncio.sleep(0.15)
                    finally:
                        self.actions.key_up(key)
                    data = await self.server.player_data(self.config.player_name)
                    if data is not None and int(data["SelectedItemSlot"]) == slot:
                        break
                    await asyncio.sleep(0.2)

    async def _start_client(self, port: int) -> None:
        if self.config.authentication == "offline":
            await self._launch_client(port)
            return
        lock_path = data_root() / "locks" / f"login-{self.config.player_uuid}.lock"
        with lock_path.open("a") as login_lock:
            async with asyncio.timeout(self.config.startup_timeout):
                while True:
                    try:
                        fcntl.flock(login_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        await asyncio.sleep(0.5)
            # Only authentication/startup is serialized; gameplay remains concurrent.
            try:
                await self._launch_client(port)
            finally:
                fcntl.flock(login_lock, fcntl.LOCK_UN)

    async def _launch_client(self, port: int) -> None:
        assert self.capture is not None and self.server is not None
        assert self._client_root is not None
        client_name = self.config.player_name
        if self.config.authentication == "offline":
            command, environment = launch_command(
                java=self._java, directory=self._client_root,
                player_name=client_name, port=port, memory_mb=self.config.memory_mb,
                structured=self.config.track == "structured_tool",
            )
            self._client = await asyncio.create_subprocess_exec(
                *command, cwd=self._client_root,
                env={**os.environ, **environment, "DISPLAY": self.config.display},
                start_new_session=True,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.PIPE if self.config.track == "structured_tool" else asyncio.subprocess.DEVNULL,
                limit=8 * 1024 * 1024,
            )
            if self.config.track == "structured_tool":
                self.bridge = NativeBridge(self._client)
        else:
            assert self._client_identity is not None
            self._client = await asyncio.create_subprocess_exec(
                "flatpak", "run", "--die-with-parent", "--env=QT_QPA_PLATFORM=xcb",
                f"--instance-id-fd={self._client_identity.fileno()}",
                f"--filesystem={prism_root()}:ro",
                PRISM_APP_ID, "--dir", str(self._client_root),
                "--launch", self.config.instance, "--profile", self.config.account or self.config.player_name,
                "--server", f"127.0.0.1:{port}",
                env={**os.environ, "DISPLAY": self.config.display},
                pass_fds=(self._client_identity.fileno(),),
                start_new_session=True,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
        self._client_errors.clear()
        self._client_reader = asyncio.create_task(self._read_client_errors())
        async with asyncio.timeout(self.config.startup_timeout):
            while True:
                self._flatpak_id = self._read_client_identity()
                if self._client.returncode is not None:
                    raise RuntimeError(
                        f"Minecraft client exited before readiness: {self._client.returncode}\n"
                        + "\n".join(self._client_errors)
                    )
                windows = self.capture.list_windows()
                if len(windows) > 1:
                    raise RuntimeError("Multiple Minecraft windows appeared; cannot bind a player safely")
                data = await self.server.player_data(client_name)
                if windows and data is not None and (
                    self.config.authentication == "offline" or self._flatpak_id is not None
                ):
                    self.window_id = windows[0].window_id
                    with_display = display.Display(self.config.display)
                    try:
                        window = with_display.create_resource_object("window", self.window_id)
                        window.configure(stack_mode=X.Above)
                        window.set_input_focus(X.RevertToParent, X.CurrentTime)
                        window.warp_pointer(windows[0].width // 2, windows[0].height // 2)
                        with_display.sync()
                    finally:
                        with_display.close()
                    self.capture.capture(self.window_id)
                    return
                await asyncio.sleep(0.5)

    async def _read_client_errors(self) -> None:
        assert self._client is not None
        native = self.config.authentication == "offline"
        stream = self._client.stdout if native else self._client.stderr
        assert stream is not None
        try:
            with (self.output / "client.log").open("w") if native else nullcontext() as log:
                while line := await stream.readline():
                    text = line.decode(errors="replace")
                    if self.bridge is not None and self.bridge.receive(text):
                        continue
                    self._client_errors.append(text.rstrip())
                    if log is not None:
                        log.write(text)
                        log.flush()
        finally:
            if self.bridge is not None:
                self.bridge.disconnected("Native client output closed; inspect client.log")

    async def _verify_player(self) -> None:
        assert self.server is not None
        actual = await self.server.player_data(self.config.player_name)
        if actual is None:
            raise RuntimeError("Player disappeared before initialization verification")
        self.state.verify(actual, self.config.player_uuid)

    async def begin_task(self) -> None:
        assert self.server is not None
        await self._verify_player()
        if self.bridge is not None:
            await self.bridge.request("resume", {})
        feedback = await self.server.command("tick unfreeze")
        if not any("The game runs normally" in line for line in feedback):
            raise RuntimeError("Could not verify unfreezing the experiment")

    async def stop_participant(self) -> None:
        if self.bridge is None:
            assert self.actions is not None
            self.actions.release_all()
            return
        await self.bridge.request("pause", {})

    def observe(self):
        assert self.server is not None and self.actions is not None and self.capture is not None
        self.server.check_ready()
        self.actions.check_ready()
        return self.capture.capture(self.window_id).image

    def _read_client_identity(self) -> str | None:
        if self._client_identity is None or self._client_identity.closed:
            return None
        raw = os.pread(self._client_identity.fileno(), 128, 0).decode("ascii").strip()
        if raw and not raw.isdecimal():
            raise RuntimeError("Flatpak returned an invalid client instance ID")
        return raw or None

    async def _stop_client(self) -> None:
        try:
            self._flatpak_id = self._flatpak_id or self._read_client_identity()
            if self._flatpak_id is not None:
                process = await asyncio.create_subprocess_exec(
                    "flatpak", "kill", self._flatpak_id,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(process.wait(), self.config.stop_timeout)
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                if process.returncode != 0 and self._flatpak_id in prism_instances():
                    raise RuntimeError("Could not stop this experiment's Prism instance")
        finally:
            try:
                if self._client is not None and self._client.returncode is None:
                    try:
                        os.killpg(self._client.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(self._client.wait(), self.config.stop_timeout)
                    except TimeoutError:
                        try:
                            os.killpg(self._client.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        await self._client.wait()
                        raise RuntimeError("Client launcher shutdown timed out; forced termination") from None
            finally:
                self._client = None
                self._flatpak_id = None
                if self._client_reader is not None:
                    await self._client_reader
                    self._client_reader = None

    async def close(self) -> None:
        await self._stack.aclose()
