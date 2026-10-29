from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import gallery


@pytest.mark.parametrize("targets,owner,expected", [
    ([0, 1], 1, False), ([0, 1, 2], 1, True), ([0, 1, 2], 2, None),
])
def test_lamps_alone_or_another_archer_do_not_satisfy_gallery(monkeypatch, targets, owner, expected):
    monkeypatch.setattr(gallery, "gallery_evidence", lambda p:
                        {"hits": [], "lamps": [0, 0, 0]} if p == Path("before") else {
                            "hits": [{"target": t, "player": [0, 0, 0, owner], "tick": 100} for t in targets],
                            "lamps": [1, 1, 1],
                        })
    monkeypatch.setattr(gallery.nbtlib, "load",
                        lambda p: {"Data": {"Time": 0 if p.parts[0] == "before" else 200}})
    monkeypatch.setattr(gallery, "evaluate_state",
                        lambda *_a, **_kw: {"success": True, "checks": [{"passed": True}], "semantics": ""})
    if expected is None:
        with pytest.raises(ValueError, match="identity"):
            gallery.evaluate_gallery(Path("before"), Path("after"), UUID(int=1), position={})
    else:
        assert gallery.evaluate_gallery(Path("before"), Path("after"), UUID(int=1), position={})["success"] is expected
