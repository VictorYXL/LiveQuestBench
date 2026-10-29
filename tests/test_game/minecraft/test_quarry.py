from uuid import UUID

import pytest

from game.minecraft.evaluators.quarry import entry_diagnostics


def test_wrong_and_repeat_entries_are_diagnostics_not_route_failures():
    events = [{"site": site, "player": [0, 0, 0, 1], "tick": 20 + i}
              for i, site in enumerate((1, 1, 2, 0))]
    result = entry_diagnostics(events, UUID(int=1), 10, 30)
    assert result["wrong_site_entries"] == 3
    assert result["distinct_sites_entered"] == [0, 1, 2]
    assert "success" not in result


@pytest.mark.parametrize("event", [
    {"site": 0, "player": [0, 0, 0, 2], "tick": 20},
    {"site": 0, "player": [0, 0, 0, 1], "tick": 31},
    {"site": 3, "player": [0, 0, 0, 1], "tick": 20},
])
def test_foreign_or_invalid_entries_are_not_attributed(event):
    with pytest.raises(ValueError, match="invalid"):
        entry_diagnostics([event], UUID(int=1), 10, 30)
