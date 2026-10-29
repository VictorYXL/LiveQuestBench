"""Offline asset-alias regression for the pinned Loom installer."""

import hashlib
from io import BytesIO
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from game.minecraft.runtime import client, install


def test_client_selection_rejects_stale_cache_without_rebuilding(tmp_path, monkeypatch):
    current_source, stale_source = "a" * 64, "b" * 64
    monkeypatch.setattr(client, "source_digest", lambda: current_source)
    user_home = tmp_path / "default"
    monkeypatch.setattr(install.Path, "home", lambda: user_home)
    roots = [user_home / ".local/share/livequestbench/minecraft", tmp_path / "matching"]
    receipts = []
    for home, source in zip(roots, (stale_source, current_source)):
        root = home / "client-1.20.4"
        support = root / ".gradle/loom-cache"
        support.mkdir(parents=True)
        for name in ("launch.cfg", "remapClasspath.txt", "log4j.xml"):
            (support / name).write_text("support")
        (root / "dependency.jar").write_bytes(b"dependency")
        launch = {"classpath": [str(root / "dependency.jar")]}
        (root / "launch.json").write_text(json.dumps(launch))
        receipt = root / "ready.json"
        receipt.write_text(json.dumps({
            "source_sha256": source, "root": str(root),
            "launch_sha256": hashlib.sha256((root / "launch.json").read_bytes()).hexdigest(),
        }))
        receipts.append((receipt, receipt.read_bytes()))

    monkeypatch.delenv("LIVEQUEST_MINECRAFT_HOME", raising=False)
    with pytest.raises(RuntimeError) as failure:
        client.check_client()
    message = str(failure.value)
    assert str(roots[0] / "client-1.20.4") in message
    assert stale_source in message and current_source in message
    assert "LIVEQUEST_MINECRAFT_HOME" in message

    monkeypatch.setenv("LIVEQUEST_MINECRAFT_HOME", str(roots[1]))
    assert client.check_client() == launch
    for path, contents in receipts:
        assert path.read_bytes() == contents
    (roots[1] / "client-1.20.4/launch.json").write_text('{"classpath": []}')
    with pytest.raises(RuntimeError, match="launch metadata changed"):
        client.check_client()
    monkeypatch.setenv("LIVEQUEST_MINECRAFT_HOME", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="not prepared"):
        client.check_client()


@pytest.mark.parametrize("failures", [1, 3])
def test_download_connection_timeout_has_bounded_retries(monkeypatch, failures):
    attempts, delays = [], []
    url = "https://downloads.gradle.org/distributions/test.zip"
    response = SimpleNamespace(geturl=lambda: url)

    def fetch(*args, **kwargs):
        attempts.append(args)
        if len(attempts) <= failures:
            raise URLError(TimeoutError("TLS handshake timed out"))
        return response

    monkeypatch.setattr(install, "urlopen", fetch)
    monkeypatch.setattr(install.time, "sleep", delays.append)
    if failures == 3:
        with pytest.raises(URLError):
            install.open_download(url, {"downloads.gradle.org"})
        assert len(attempts) == 3 and delays == [10, 20]
    else:
        assert install.open_download(url, {"downloads.gradle.org"}) is response
        assert len(attempts) == 2 and delays == [10]


def test_download_does_not_retry_http_permission_failure(monkeypatch):
    url = "https://downloads.gradle.org/distributions/test.zip"

    def fetch(*args, **kwargs):
        raise HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(install, "urlopen", fetch)
    monkeypatch.setattr(install.time, "sleep", lambda _: pytest.fail("403 must not be retried"))
    with pytest.raises(HTTPError):
        install.open_download(url, {"downloads.gradle.org"})


def test_asset_aliases_are_verified_and_downloaded_only_once(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVEQUEST_MINECRAFT_HOME", str(tmp_path))
    data = b"shared asset"
    digest = hashlib.sha1(data).hexdigest()
    index = json.dumps({"objects": {
        "first": {"hash": digest, "size": len(data)},
        "alias": {"hash": digest, "size": len(data)},
        "unique": {"hash": "a" * 40, "size": 10},
    }}).encode()
    url = "https://piston-meta.mojang.com/assets.json"
    asset_url = f"https://resources.download.minecraft.net/{digest[:2]}/{digest}"
    monkeypatch.setattr(client, "version_metadata", lambda: {"assetIndex": {
        "url": url, "sha1": hashlib.sha1(index).hexdigest(), "size": len(index),
    }})
    requests = []

    def fetch(request_url, hosts):
        requests.append(request_url)
        return BytesIO({url: index, asset_url: data}[request_url])

    monkeypatch.setattr(install, "open_download", fetch)
    client.prepare_shared_assets()
    assert requests == [url, asset_url]
    target = tmp_path / "gradle/caches/fabric-loom/assets/objects" / digest[:2] / digest
    assert target.read_bytes() == data
    client.prepare_shared_assets()
    assert requests == [url, asset_url]
    target.write_bytes(b"corrupt data")
    client.prepare_shared_assets()
    assert requests == [url, asset_url, asset_url]
    assert target.read_bytes() == data


def test_conflicting_asset_alias_sizes_fail_before_object_download(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVEQUEST_MINECRAFT_HOME", str(tmp_path))
    index = json.dumps({"objects": {
        "first": {"hash": "a" * 40, "size": 1},
        "alias": {"hash": "a" * 40, "size": 2},
    }}).encode()
    monkeypatch.setattr(client, "version_metadata", lambda: {"assetIndex": {
        "url": "https://piston-meta.mojang.com/assets.json",
        "sha1": hashlib.sha1(index).hexdigest(), "size": len(index),
    }})
    monkeypatch.setattr(install, "open_download", lambda *_: BytesIO(index))
    with pytest.raises(ValueError, match="aliases disagree"):
        client.prepare_shared_assets()
    assert not (tmp_path / "gradle").exists()
