from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.database import Database


def make_db(tmp_path):
    return Database(str(tmp_path / "analytics.db"))


def test_shot_event_insert_and_overview(tmp_path):
    db = make_db(tmp_path)
    now = datetime.now() - timedelta(minutes=5)

    db.insert_shot_event(
        {
            "game_id": "game_test",
            "player_name": "Alex",
            "shot_index": 1,
            "created_at": now.isoformat(),
            "mode": "practice_single",
            "target_ball": 1,
            "first_contact": 1,
            "potted_balls": [1],
            "pocket_result": "made",
            "cue_ball_potted": False,
            "is_foul": False,
            "thickness_result": "on_line",
            "distance_bucket": "near",
            "difficulty_level": "easy",
            "success_prob": 0.8,
            "position_success_prob": 0.7,
            "planned_cue_landing": [100, 100],
            "actual_cue_landing": [108, 106],
            "cue_landing_error_px": 10.0,
            "next_ball_quality": "good",
        }
    )
    db.insert_shot_event(
        {
            "player_name": "Alex",
            "shot_index": 2,
            "created_at": (now + timedelta(seconds=3)).isoformat(),
            "mode": "practice_single",
            "pocket_result": "missed",
            "cue_ball_potted": True,
            "is_foul": True,
            "foul_reason": "母球進袋",
            "thickness_result": "too_thin",
            "distance_bucket": "far",
            "difficulty_level": "hard",
            "position_success_prob": 0.2,
        }
    )

    overview = db.get_analytics_overview("Alex", "today")

    assert overview["has_data"] is True
    assert overview["today_shots"] == 2
    assert overview["pocket_rate"] == 0.5
    assert overview["scratch_count"] == 1
    assert overview["best_streak"] == 1
    assert overview["most_common_mistake"]["type"] == "scratch"
    assert overview["performance_score"] is not None


def test_analytics_empty_payload(tmp_path):
    db = make_db(tmp_path)

    overview = db.get_analytics_overview("Nobody", "today")
    offense = db.get_analytics_offense("Nobody", "today")
    trends = db.get_analytics_trends("Nobody", "day")

    assert overview["has_data"] is False
    assert overview["performance_score"] is None
    assert overview["confidence"] == "empty"
    assert offense["has_data"] is False
    assert trends["has_data"] is False
    assert trends["points"] == []


def test_existing_player_stats_still_empty_for_unknown_player(tmp_path):
    db = make_db(tmp_path)

    stats = db.get_player_analytics("不存在的玩家")

    assert stats["name"] == "不存在的玩家"
    assert stats["total_games"] == 0
    assert stats["total_wins"] == 0
    assert stats["win_rate"] == 0.0
