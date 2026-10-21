"""Shared command-line switches for local game tests."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("game display")
    group.addoption("--headless", action="store_true", dest="game_headless", default=True,
                    help="Run game tests on owned virtual displays (default)")
    group.addoption("--no-headless", action="store_false", dest="game_headless",
                    help="Show game tests on the existing X11 DISPLAY; do not use the window manually")


@pytest.fixture
def headless(request: pytest.FixtureRequest) -> bool:
    value = request.config.getoption("game_headless")
    assert isinstance(value, bool)
    return value
