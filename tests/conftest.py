"""Shared command-line switches for local game tests."""

import os
from pathlib import Path

import pytest
from benchmark.config import load_task


@pytest.fixture
def minecraft_world_path() -> Path:
    return Path(os.environ["MINECRAFT_TEST_FIXTURE"]) if os.environ.get("MINECRAFT_TEST_FIXTURE") else (
        Path(__file__).resolve().parents[1] / "output/back/legacy-config-20261026/config/minecraft/fixtures/island"
    )


@pytest.fixture
def veloren_fixture() -> dict:
    return load_task(Path(__file__).resolve().parents[1] / "output/back/legacy-config-20261026/config/veloren/tasks/structured_tools/move_2_metres.yaml").fixture


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("game display")
    group.addoption("--headless", action="store_true", dest="game_headless", default=True,
                    help="Run game tests on owned virtual displays (default)")
    group.addoption("--no-headless", action="store_false", dest="game_headless",
                    help="Show game tests on the existing X11 DISPLAY; do not use the window manually")
    group.addoption("--recording", action="store_true", dest="game_recording", default=None,
                    help="Record game tests (default); overrides MINECRAFT_TEST_RECORDING")
    group.addoption("--no-recording", action="store_false", dest="game_recording",
                    help="Disable test videos without disabling rendering or observations")


@pytest.fixture
def headless(request: pytest.FixtureRequest) -> bool:
    value = request.config.getoption("game_headless")
    assert isinstance(value, bool)
    return value


@pytest.fixture
def recording(request: pytest.FixtureRequest) -> bool:
    value = request.config.getoption("game_recording")
    if value is None:
        return os.environ.get("MINECRAFT_TEST_RECORDING", "1") != "0"
    assert isinstance(value, bool)
    return value
