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


def test_visual_remaining_can_advance_current_target_when_protection_disabled():
    manager = GameManager()
    manager.start_nine_ball()

    result = manager.apply_visual_remaining_balls(
        [2, 3, 4, 5, 6, 7, 8, 9],
        protect_current_target=False,
    )

    assert result["target_ball"] == 2
    assert result["remaining_balls"][0] == 2
    assert result["remaining_balls_source"] == "vision"
    assert manager.game_state is not None
    assert manager.game_state.target_ball == 2


def test_visual_remaining_can_follow_rules_after_target_was_potted():
    manager = GameManager()
    manager.start_nine_ball()
    manager.check_nine_ball_rules(first_contact=1, potted_ball=1)

    result = manager.apply_visual_remaining_balls([2, 3, 4, 5, 6, 7, 8, 9])

    assert result["target_ball"] == 2
    assert result["remaining_balls"][0] == 2
    assert manager.game_state is not None
    assert manager.game_state.target_ball == 2


def test_auto_shot_target_potted_advances_target_and_keeps_turn():
    manager = GameManager()
    manager.start_nine_ball()
    assert manager.game_state is not None
    manager.game_state.remaining_balls = [1, 2]
    manager.game_state.target_ball = 1

    result = manager.apply_auto_shot_result(
        first_contact=1,
        potted_balls=[1],
        cue_ball_potted=False,
    )

    assert result["continue_turn"] is True
    assert result["potted_balls"] == [1]
    assert manager.game_state.remaining_balls == [2]
    assert manager.game_state.target_ball == 2


def test_auto_shot_wrong_first_contact_records_foul_result():
    manager = GameManager()
    manager.start_nine_ball()
    assert manager.game_state is not None

    result = manager.apply_auto_shot_result(
        first_contact=2,
        potted_balls=[],
        cue_ball_potted=False,
    )

    assert result["is_foul"] is True
    assert result["foul_reason"] == "未先擊中目標球 #1"
    assert manager.game_state.foul_detected is True
    assert manager.game_state.foul_reason == "未先擊中目標球 #1"
    assert manager.game_state.last_shot_result == result


def test_auto_shot_no_first_contact_records_foul_result():
    manager = GameManager()
    manager.start_nine_ball()
    assert manager.game_state is not None

    result = manager.apply_auto_shot_result(
        first_contact=None,
        potted_balls=[],
        cue_ball_potted=False,
    )

    assert result["is_foul"] is True
    assert result["first_contact"] is None
    assert result["foul_reason"] == "未先擊中目標球 #1"
    assert manager.game_state.foul_detected is True
    assert manager.game_state.last_shot_result == result
