import asyncio
from types import SimpleNamespace

import pytest

from game.veloren.game import VelorenGame
from game.veloren.structured_tools.interface import FIELDS, project


def test_energy_is_explicit_native_readout_without_private_fields():
    row = {field: None for field in FIELDS}
    row["energy"] = {"current": 47.25, "maximum": 100.0, "fraction": .4725, "private": "excluded"}
    row["private_encounter_evidence"] = {"secret": True}
    assert "energy" not in project(row)
    visible = project(row, energy=True)
    assert visible["energy"] == {"current": 47.25, "maximum": 100.0, "fraction": .4725}
    assert "private_encounter_evidence" not in visible
    del row["energy"]
    with pytest.raises(ValueError, match="energy"):
        project(row, energy=True)


@pytest.mark.parametrize("enabled", [False, True])
def test_fixture_controls_public_energy_projection(tmp_path, veloren_fixture, enabled):
    fixture = {**veloren_fixture, "public_energy": enabled}
    game = VelorenGame(output_dir=tmp_path / "game", fixture=fixture, track="structured_tool")
    game.phase = "running"
    row = {field: None for field in FIELDS}
    row["energy"] = {"current": 61.0, "maximum": 100.0, "fraction": .61}

    async def request(operation):
        assert operation == "observe"
        return row

    game._session = SimpleNamespace(check_ready=lambda: None, request=request)
    observed = asyncio.run(game.get_agent_interface().observe())
    assert ("energy" in observed) is enabled
    if enabled:
        assert observed["energy"]["current"] == 61.0
