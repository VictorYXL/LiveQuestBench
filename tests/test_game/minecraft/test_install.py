"""Offline asset-alias regression for the pinned Loom installer."""

import hashlib
from io import BytesIO
import json

import pytest

from game.minecraft.runtime import client, install


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
