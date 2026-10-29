import pytest

from game.minecraft.evaluators import timed_routing


def test_original_consignment_cannot_be_substituted_at_admission(monkeypatch):
    rows = [{"Tags": ["original_cart_"+name],
             "Items": [{"tag": {"livequest_cargo": name+"_consignment"}}]}
            for name in ("east", "west")]
    monkeypatch.setattr(timed_routing, "entities", lambda _: rows)
    timed_routing.verify_initial(None)
    rows[1]["Items"] = rows[0]["Items"]
    with pytest.raises(ValueError, match="consignment"):
        timed_routing.verify_initial(None)
