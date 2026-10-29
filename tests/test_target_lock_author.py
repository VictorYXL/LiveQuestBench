import re

from scripts import author_target_lock


def test_feedback_counter_refills_never_manufacture_goal_tokens(monkeypatch):
    monkeypatch.setenv("LQ_NATIVE_LOWER", "4")
    feedback, tokens = 0, 0
    for command in author_target_lock.commands():
        match = re.match(r"(?:setblock|data merge block) 25 73 (-?\d+) (.+)", command)
        if not match:
            continue
        z, contents = int(match[1]), match[2]
        if z in (-5, 5, 15, 25):
            feedback += 1
            assert "livequest_token" not in contents
        elif z in (8, 28):
            tokens += 1
            assert "livequest_token" in contents
            assert "Count:1b" in contents
    assert feedback and tokens


def test_original_token_stores_cannot_be_reached_through_collection_apertures():
    for command in author_target_lock.commands():
        if "livequest_token" not in command:
            continue
        position = re.match(r"(?:setblock|data merge block) (-?\d+) 73 (-?\d+) ", command)
        assert position is not None
        assert int(position[1]) - 16 > 5
