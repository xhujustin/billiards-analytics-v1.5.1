import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tracking.game_manager import GameManager  # noqa: E402


def test_visual_remaining_does_not_advance_current_target_from_missing_detection():
    manager = GameManager()
    manager.start_nine_ball()

    result = manager.apply_visual_remaining_balls([2, 3, 4, 5, 6, 7, 8, 9])

    assert result["target_ball"] == 1
    assert result["remaining_balls"][0] == 1
    assert manager.game_state is not None
    assert manager.game_state.target_ball == 1


def test_visual_remaining_can_follow_rules_after_target_was_potted():
    manager = GameManager()
    manager.start_nine_ball()
    manager.check_nine_ball_rules(first_contact=1, potted_ball=1)

    result = manager.apply_visual_remaining_balls([2, 3, 4, 5, 6, 7, 8, 9])

    assert result["target_ball"] == 2
    assert result["remaining_balls"][0] == 2
    assert manager.game_state is not None
    assert manager.game_state.target_ball == 2
