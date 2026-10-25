"""Verify or provision Minecraft dependencies without launching a game."""

from __future__ import annotations

import argparse
import hashlib
from importlib.util import find_spec
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen


MINECRAFT_VERSION = "1.20.4"
PRISM_APP_ID = "org.prismlauncher.PrismLauncher"
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_HOSTS = {
    "piston-meta.mojang.com", "piston-data.mojang.com",
    "launcher.mojang.com", "launchermeta.mojang.com",
}
INSTANCE_ID = "1.20.4"


def data_root() -> Path:
    return Path(os.environ.get(
        "LIVEQUEST_MINECRAFT_HOME",
        str(Path.home() / ".local" / "share" / "livequestbench" / "minecraft"),
    )).expanduser().resolve()


def server_jar() -> Path:
    explicit = os.environ.get("MINECRAFT_SERVER_JAR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    own = data_root() / "downloads" / f"server-{MINECRAFT_VERSION}.jar"
    if own.is_file():
        return own
    legacy = Path(os.environ.get(
        "GAMEAGENTVISUAL_HOME", str(Path.home() / ".local/share/gameagentvisual"),
    )).expanduser() / "downloads" / f"server-{MINECRAFT_VERSION}.jar"
    return legacy if legacy.is_file() else own


def prism_root() -> Path:
    return Path(os.environ.get(
        "MINECRAFT_PRISM_ROOT",
        str(Path.home() / ".var" / "app" / PRISM_APP_ID / "data" / "PrismLauncher"),
    )).expanduser().resolve()


def check_platform() -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("This initial installer supports Linux x86_64 only.")


def check_java() -> str:
    executable = os.environ.get("MINECRAFT_JAVA", "java")
    result = subprocess.run(
        [executable, "-version"], capture_output=True, text=True,
        timeout=10, check=True,
    )
    if not re.search(r'version "21(?:[."])', result.stdout + result.stderr):
        raise RuntimeError("Server requires Java 21; set MINECRAFT_JAVA to its executable.")
    return executable


def open_download(url: str, hosts: set[str]):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https" or parsed.hostname not in hosts
        or parsed.username or parsed.password or parsed.port not in (None, 443)
    ):
        raise ValueError("Download URL must use an approved HTTPS host.")
    response = urlopen(url, timeout=60)
    final = urlparse(response.geturl())
    if final.scheme != "https" or final.hostname not in hosts:
        response.close()
        raise ValueError("Download redirected outside approved HTTPS hosts.")
    return response


def file_digest(path: Path, algorithm: str) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, algorithm).hexdigest()


def download(
    url: str, target: Path, *, algorithm: str, digest: str,
    size: int, hosts: set[str],
) -> None:
    if not re.fullmatch(r"[0-9a-f]{" + str(hashlib.new(algorithm).digest_size * 2) + "}", digest):
        raise ValueError("Invalid artifact digest.")
    if type(size) is not int or not 0 < size <= 512 * 1024 * 1024:
        raise ValueError("Invalid artifact size.")
    if target.is_file() and target.stat().st_size == size:
        if file_digest(target, algorithm) == digest:
            print(f"Verified cached artifact: {target}", flush=True)
            return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".download-", dir=target.parent) as staging:
        temporary = Path(staging) / "artifact"
        count = 0
        print(f"Downloading {target.name}", flush=True)
        with open_download(url, hosts) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > size:
                    raise ValueError("Download exceeds expected size.")
                output.write(chunk)
        if count != size or file_digest(temporary, algorithm) != digest:
            raise ValueError("Artifact size/hash mismatch; existing installation is unchanged.")
        temporary.replace(target)


def version_metadata() -> dict:
    with open_download(MANIFEST_URL, MOJANG_HOSTS) as response:
        manifest = json.loads(response.read(8 * 1024 * 1024))
    entry = next(
        item for item in manifest["versions"]
        if item["id"] == MINECRAFT_VERSION and item["type"] == "release"
    )
    with open_download(entry["url"], MOJANG_HOSTS) as response:
        metadata_bytes = response.read(8 * 1024 * 1024)
    if hashlib.sha1(metadata_bytes).hexdigest() != entry["sha1"]:
        raise ValueError("Minecraft version metadata hash mismatch.")
    metadata = json.loads(metadata_bytes)
    if metadata["id"] != MINECRAFT_VERSION:
        raise ValueError("Minecraft version mismatch.")
    return metadata


def server_artifact() -> dict:
    return version_metadata()["downloads"]["server"]


def install_server(root: Path) -> Path:
    artifact = server_artifact()
    target = server_jar()
    if not target.is_file() and not os.environ.get("MINECRAFT_SERVER_JAR"):
        target = root / "downloads" / f"server-{MINECRAFT_VERSION}.jar"
    if target.is_file():
        if target.stat().st_size != artifact["size"] or file_digest(target, "sha1") != artifact["sha1"]:
            raise ValueError(f"Existing server artifact failed verification; not overwriting: {target}")
        print(f"Verified existing server: {target}")
        return target
    download(
        artifact["url"], target, algorithm="sha1", digest=artifact["sha1"],
        size=artifact["size"], hosts=MOJANG_HOSTS,
    )
    return target


def check_prism() -> None:
    try:
        subprocess.run(
            ["flatpak", "info", PRISM_APP_ID],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            f"Flatpak Prism Launcher ({PRISM_APP_ID}) is unavailable. "
            "Explicit online VM requires a separately prepared Prism installation. "
            "The default local offline VM does not require Prism."
        ) from exc


def check_instance(instance_id: str) -> None:
    if not instance_id or instance_id in {".", ".."} or "/" in instance_id or "\\" in instance_id:
        raise ValueError("Prism instance ID must be a single instance folder name.")
    instance = prism_root() / "instances" / instance_id
    manifest = instance / "mmc-pack.json"
    if not manifest.is_file() or not (instance / "instance.cfg").is_file():
        raise RuntimeError(
            f"Prism instance {instance_id!r} is missing or incomplete at {instance}. "
            "Open the client launcher and create a Minecraft 1.20.4 instance, "
            "or select its folder name with --instance."
        )
    pack = json.loads(manifest.read_text(encoding="utf-8"))
    components = pack.get("components") if isinstance(pack, dict) else None
    if not isinstance(components, list):
        raise ValueError(f"Invalid Prism instance manifest: {manifest}")
    versions = [
        item.get("version") for item in components
        if isinstance(item, dict) and item.get("uid") == "net.minecraft"
    ]
    if versions != [MINECRAFT_VERSION]:
        raise ValueError(f"Prism instance {instance_id!r} must use Minecraft {MINECRAFT_VERSION}.")


def install(root: Path, track: str = "visual_motor") -> None:
    check_platform()
    check_java()
    from game.minecraft.runtime.client import install_client
    install_client()
    install_server(root)
    print(
        f"Minecraft {MINECRAFT_VERSION} server artifact is ready.\n"
        f"Selected setup: {track}.\n"
        "No server started and no EULA accepted.\n"
        "Existing client instances and account data were not modified."
    )


def check_installation(
    instance: str = INSTANCE_ID, *, verify_server: bool = False, track: str = "visual_motor",
    authentication: str = "offline",
) -> dict:
    if track not in ("visual_motor", "structured_tool", "all"):
        raise ValueError("Unknown Minecraft track")
    check_platform()
    for module in ("PIL", "Xlib", "nbtlib"):
        if find_spec(module) is None:
            raise RuntimeError(f"Missing Python dependency {module}; run uv sync --locked --extra minecraft")
    java = check_java()
    client_build = None
    if authentication not in ("offline", "online"):
        raise ValueError("Unknown Minecraft authentication mode")
    if track == "structured_tool" and authentication != "offline":
        raise ValueError("ST supports local offline authentication only")
    if authentication == "online":
        check_prism()
        check_instance(instance)
    else:
        from game.minecraft.runtime.client import check_client, source_digest
        check_client()
        client_build = source_digest()
    for program in ("Xvfb", "ffmpeg"):
        if shutil.which(program) is None:
            raise RuntimeError(f"Missing executable: {program}")
    jar = server_jar()
    if not jar.is_file():
        raise FileNotFoundError("Minecraft server missing; run game/minecraft/setup.sh")
    artifact = server_artifact() if verify_server else None
    if artifact and (jar.stat().st_size != artifact["size"] or file_digest(jar, "sha1") != artifact["sha1"]):
        raise ValueError("Server artifact does not match Mojang's Minecraft 1.20.4 metadata")
    if track != "structured_tool" and authentication == "online":
        for name in ("assets", "libraries", "java", "meta"):
            if not (prism_root() / name).is_dir():
                raise FileNotFoundError(f"Prism resource cache missing: {name}")
        for name in ("accounts.json", "prismlauncher.cfg", "metacache"):
            if not (prism_root() / name).is_file():
                raise FileNotFoundError(f"Prism setup incomplete: missing {name}")
    return {
        "version": MINECRAFT_VERSION, "java": java, "server_jar": str(jar),
        "server_sha256": file_digest(jar, "sha256"), "verified_with_mojang": verify_server,
        "track": track,
        **({"instance": instance, "prism_root": str(prism_root())}
           if track != "structured_tool" and authentication == "online" else {}),
        "client": "prism" if authentication == "online" else "fabric-development",
        **({"client_build_sha256": client_build} if client_build is not None else {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "install"))
    parser.add_argument("--instance", default=INSTANCE_ID)
    parser.add_argument("--track", choices=("visual_motor", "structured_tool", "all"), default="visual_motor")
    parser.add_argument("--verify-server", action="store_true",
                        help="Read official metadata and verify the server artifact; no writes")
    args = parser.parse_args()
    if args.command == "install":
        install(data_root(), args.track)
    else:
        print(json.dumps(check_installation(args.instance, verify_server=args.verify_server, track=args.track), indent=2))


if __name__ == "__main__":
    main()
