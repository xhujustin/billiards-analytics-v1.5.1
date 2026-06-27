import os
import json
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Awaitable, Callable
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

import config
from auth.account_store import AccountError, AccountStore
from auth.account_store_factory import create_account_store
from database.database import Database
from storage.supabase_accounts import SupabaseAccountError
from storage.supabase_analytics import SupabaseAnalyticsError, configured_supabase_analytics_repository
from storage.supabase_blocks import SupabaseBlockError, configured_supabase_block_repository
from storage.supabase_follows import SupabaseFollowError, configured_supabase_follow_repository
from storage.supabase_friend_match import SupabaseFriendMatchError, configured_supabase_friend_match_repository
from storage.supabase_notifications import SupabaseNotificationError, configured_supabase_notification_repository
from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository
from services.mobile_push_notifications import MobilePushEvent, configured_mobile_push_notification_service


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = create_account_store(db_path, int(getattr(config, "AUTH_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)))
db = Database(db_path)
router = APIRouter()

StartFriendGameHandler = Callable[[str, str], Awaitable[dict[str, Any]]]
start_friend_game_handler: StartFriendGameHandler | None = None


class MobileProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    is_private: bool | None = None


class NotificationSettingsUpdateRequest(BaseModel):
    push_enabled: bool | None = None
    post_likes_enabled: bool | None = None
    post_comments_enabled: bool | None = None
    comment_replies_enabled: bool | None = None
    comment_likes_enabled: bool | None = None
    new_followers_enabled: bool | None = None
    mutual_follows_enabled: bool | None = None
    account_security_enabled: bool | None = None
    login_changes_enabled: bool | None = None
    service_announcements_enabled: bool | None = None
    show_preview_enabled: bool | None = None
    type_only_enabled: bool | None = None
    quiet_hours_enabled: bool | None = None


class PushTokenRequest(BaseModel):
    expo_push_token: str
    device: str = ""
    platform: str = ""


class FriendCodeStartGameRequest(BaseModel):
    code: str


class LocalFriendStartGameRequest(BaseModel):
    name: str


class FriendInviteQrCreateRequest(BaseModel):
    base_url: str | None = None


class FriendInviteQrAcceptRequest(BaseModel):
    payload: str | None = None
    token: str | None = None


class FriendMatchInviteCreateRequest(BaseModel):
    host_player: str
    game_type: str = "nine_ball"
    target_rounds: int = 5
    shot_time_limit: int = 0


def set_start_friend_game_handler(handler: StartFriendGameHandler) -> None:
    global start_friend_game_handler
    start_friend_game_handler = handler


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _current_user(authorization: str | None) -> dict[str, Any]:
    token = _extract_token(authorization)
    try:
        user = account_store.authenticate_token(token)
    except SupabaseAccountError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "ACCOUNT_STORE_ERROR", "message": str(exc)},
        ) from exc
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return user


def _account_error_response(error: AccountError) -> HTTPException:
    status_code = 400
    if error.code == "USER_NOT_FOUND":
        status_code = 404
    if error.code in {"INVALID_FRIEND_INVITE", "FRIEND_INVITE_EXPIRED"}:
        status_code = 400
    if error.code == "FRIEND_REQUIRED":
        status_code = 403
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message})


def _notification_repo_or_error():
    repo = configured_supabase_notification_repository()
    if repo is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Supabase notification settings are not configured."},
        )
    return repo


def _dispatch_mobile_push_notification(event: MobilePushEvent) -> None:
    service = configured_mobile_push_notification_service()
    if service is None:
        return
    try:
        service.dispatch(event)
    except Exception as exc:
        print(f"WARNING mobile push notification dispatch failed: {exc}")


def _actor_display_name(user: dict[str, Any]) -> str:
    return str(user.get("display_name") or user.get("username") or "使用者")


def _derive_player_level(analytics: dict[str, Any]) -> str:
    total_games = int(analytics.get("total_games") or 0)
    win_rate = float(analytics.get("win_rate") or 0)
    if total_games >= 60 and win_rate >= 0.6:
        return "進階玩家 II"
    if total_games >= 30:
        return "進階玩家 I"
    if total_games >= 10:
        return "新手玩家 III"
    if total_games > 0:
        return "新手玩家 II"
    return "新手玩家 I"


def _is_official_mobile_user(user: dict[str, Any]) -> bool:
    username = str(user.get("username") or "").strip().casefold()
    display_name = str(user.get("display_name") or "").strip().casefold()
    return username == "cuevex" or display_name in {"cuevex", "cuevex 官方"}


def _player_level_for_user(user: dict[str, Any], analytics: dict[str, Any]) -> str:
    return "官方帳號" if _is_official_mobile_user(user) else _derive_player_level(analytics)


def _player_analytics(player_name: str) -> dict[str, Any]:
    repo = configured_supabase_analytics_repository()
    if repo is not None:
        try:
            return repo.get_player_analytics(player_name)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics mobile dashboard read failed; using SQLite: {exc}")
    return db.get_player_analytics(player_name)


def _analytics_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _taipei_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _taipei_cutoff(days: int) -> str:
    return (_taipei_now() - timedelta(days=days)).replace(tzinfo=None).isoformat()


def _taipei_week_bucket(value: Any) -> str:
    parsed = _recording_datetime(value)
    if parsed is None:
        return ""
    year, week, _ = parsed.isocalendar()
    return f"{year}-W{week:02d}"


def _taipei_iso(value: Any) -> str | None:
    parsed = _recording_datetime(value)
    if parsed is None:
        return None
    return parsed.replace(tzinfo=None).isoformat()


def _joined_days(created_at: Any) -> int:
    joined_at = _parse_datetime(created_at)
    if joined_at is None:
        return 1
    if joined_at.tzinfo is None:
        joined_at = joined_at.replace(tzinfo=timezone(timedelta(hours=8)))
    now = _taipei_now()
    return max(1, (now.date() - joined_at.astimezone(timezone(timedelta(hours=8))).date()).days + 1)


def _practice_mix_for_player(player_name: str) -> dict[str, int]:
    records = _practice_recordings_for_player(player_name)
    shot_events = _shot_events_for_player(player_name)
    recent_30_start = _taipei_now() - timedelta(days=30)
    recent_7_start = _taipei_now() - timedelta(days=7)

    def is_recent(item: dict[str, Any], cutoff: datetime) -> bool:
        started_at = _recording_datetime(item.get("start_time"))
        return started_at is not None and started_at >= cutoff

    return {
        "total": len(records),
        "single": sum(1 for item in records if item.get("game_type") == "practice_single"),
        "pattern": sum(1 for item in records if item.get("game_type") == "practice_pattern"),
        "accuracy": sum(1 for item in records if item.get("game_type") == "practice_accuracy"),
        "recent_30": sum(1 for item in records if is_recent(item, recent_30_start)),
        "recent_7": sum(1 for item in records if is_recent(item, recent_7_start)),
        "events": len(shot_events),
    }


def _practice_overview_for_player(player_name: str) -> dict[str, Any]:
    records = _practice_recordings_for_player(player_name)
    week_start = _taipei_now() - timedelta(days=7)
    weekly_seconds = sum(
        float(item.get("duration_seconds") or 0)
        for item in records
        if (started_at := _recording_datetime(item.get("start_time"))) is not None and started_at >= week_start
    )
    analytics = _player_analytics(player_name)

    return {
        "total_practice_sessions": len(records),
        "weekly_practice_hours": round(weekly_seconds / 3600, 1),
        "total_battle_matches": int(analytics.get("total_games") or 0),
    }


def _recording_belongs_to_player(item: dict[str, Any], player_name: str) -> bool:
    player1 = str(item.get("player1_name") or "").strip()
    player2 = str(item.get("player2_name") or "").strip()
    return player1 == player_name or player2 == player_name or (not player1 and not player2)


def _recording_datetime(value: Any) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
    return parsed.astimezone(timezone(timedelta(hours=8)))


def _practice_recordings_for_player(player_name: str) -> list[dict[str, Any]]:
    game_types = ["practice_single", "practice_pattern", "practice_accuracy"]
    repo = configured_supabase_analytics_repository()
    if repo is not None:
        try:
            recordings, _ = repo.get_recordings(game_types=game_types, limit=1000, offset=0)
            return [
                item for item in recordings
                if _recording_belongs_to_player(item, player_name)
            ]
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics mobile practice read failed; using SQLite: {exc}")

    with db.transaction() as conn:
        rows = conn.execute(
            """
            SELECT game_id, game_type, start_time, duration_seconds, player1_name, player2_name
            FROM recordings
            WHERE game_type IN ('practice_single', 'practice_pattern', 'practice_accuracy')
              AND (player1_name = ? OR player2_name = ? OR (COALESCE(player1_name, '') = '' AND COALESCE(player2_name, '') = ''))
            ORDER BY start_time DESC
            LIMIT 1000
            """,
            (player_name, player_name),
        ).fetchall()
    return [dict(row) for row in rows]


def _shot_events_for_player(player_name: str) -> list[dict[str, Any]]:
    repo = configured_supabase_analytics_repository()
    if repo is not None:
        try:
            return repo.get_shot_events(player_name=player_name, limit=1000)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics mobile shot events read failed; using SQLite: {exc}")

    return [
        item for item in db.get_shot_events(player_name=None)
        if _shot_event_belongs_to_player(item, player_name)
    ]


def _ball_shape_summary_from_recordings(recordings: list[dict[str, Any]], player_name: str) -> dict[str, Any]:
    pattern_records = [
        item for item in recordings
        if item.get("game_type") == "practice_pattern" and _recording_belongs_to_player(item, player_name)
    ]
    pattern_records.sort(key=lambda item: str(item.get("start_time") or ""), reverse=True)
    now = _taipei_now()
    week_start = now - timedelta(days=7)
    total_duration = sum(float(item.get("duration_seconds") or 0) for item in pattern_records)
    weekly_count = 0
    for item in pattern_records:
        started_at = _recording_datetime(item.get("start_time"))
        if started_at is not None and started_at >= week_start:
            weekly_count += 1

    return {
        "status": "ready" if pattern_records else "empty",
        "total_sessions": len(pattern_records),
        "weekly_sessions": weekly_count,
        "total_duration_seconds": round(total_duration, 2),
        "latest_practice_at": _taipei_iso(pattern_records[0].get("start_time")) if pattern_records else None,
        "recent_records": [
            {
                "game_id": item.get("game_id"),
                "duration_seconds": item.get("duration_seconds") or 0,
                "date": _taipei_iso(item.get("start_time")) or item.get("start_time"),
            }
            for item in pattern_records[:5]
        ],
    }


def _ball_shape_summary_for_player(player_name: str) -> dict[str, Any]:
    return _ball_shape_summary_from_recordings(_practice_recordings_for_player(player_name), player_name)


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _shot_event_belongs_to_player(item: dict[str, Any], player_name: str) -> bool:
    event_player = str(item.get("player_name") or "").strip()
    return event_player == player_name or not event_player


def _shot_event_is_made(item: dict[str, Any]) -> bool:
    return str(item.get("pocket_result") or "").strip() == "made" or bool(_json_list(item.get("potted_balls")))


def _offense_summary_from_events(events: list[dict[str, Any]], player_name: str) -> dict[str, Any]:
    player_events = [item for item in events if _shot_event_belongs_to_player(item, player_name)]
    player_events.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    now = _taipei_now()
    week_start = now - timedelta(days=7)
    weekly_events: list[dict[str, Any]] = []
    for item in player_events:
        created_at = _recording_datetime(item.get("created_at"))
        if created_at is not None and created_at >= week_start:
            weekly_events.append(item)

    made_count = sum(1 for item in weekly_events if _shot_event_is_made(item))
    shot_count = len(weekly_events)
    pot_rate = round((made_count / shot_count) * 100, 1) if shot_count else None
    total_made = sum(1 for item in player_events if _shot_event_is_made(item))

    return {
        "status": "ready" if player_events else "empty",
        "weekly_shot_count": shot_count,
        "weekly_made_count": made_count,
        "weekly_pot_rate": pot_rate,
        "total_shot_count": len(player_events),
        "total_made_count": total_made,
        "scratch_count": sum(1 for item in weekly_events if bool(item.get("cue_ball_potted"))),
        "foul_count": sum(1 for item in weekly_events if bool(item.get("is_foul"))),
        "latest_shot_at": _taipei_iso(player_events[0].get("created_at")) if player_events else None,
        "recent_records": [
            {
                "game_id": item.get("game_id"),
                "shot_index": int(item.get("shot_index") or 0),
                "created_at": _taipei_iso(item.get("created_at")) or item.get("created_at"),
                "target_ball": item.get("target_ball"),
                "pocket_result": item.get("pocket_result") or "missed",
                "potted_balls": _json_list(item.get("potted_balls")),
                "difficulty_level": item.get("difficulty_level") or "unknown",
                "distance_bucket": item.get("distance_bucket") or "unknown",
                "is_foul": bool(item.get("is_foul")),
            }
            for item in player_events[:5]
        ],
    }


def _offense_summary_for_player(player_name: str) -> dict[str, Any]:
    return _offense_summary_from_events(_shot_events_for_player(player_name), player_name)


def _weekly_shot_count_for_player(player_name: str) -> int:
    week_start = _taipei_now() - timedelta(days=7)
    return sum(
        1 for item in _shot_events_for_player(player_name)
        if (created_at := _recording_datetime(item.get("created_at"))) is not None and created_at >= week_start
    )


def _practice_weekly_series_for_player(player_name: str, weeks: int = 8) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in _practice_recordings_for_player(player_name):
        started_at = _recording_datetime(item.get("start_time"))
        if started_at is None:
            continue
        bucket = _taipei_week_bucket(item.get("start_time"))
        if not bucket:
            continue
        date_label = started_at.date().isoformat()
        entry = grouped.setdefault(bucket, {
            "bucket": bucket,
            "week_start": date_label,
            "week_end": date_label,
            "sessions": 0,
            "seconds": 0.0,
        })
        entry["sessions"] += 1
        entry["seconds"] += float(item.get("duration_seconds") or 0)
        entry["week_start"] = min(str(entry["week_start"]), date_label)
        entry["week_end"] = max(str(entry["week_end"]), date_label)

    ordered = [
        grouped[bucket]
        for bucket in sorted(grouped.keys(), reverse=True)[:weeks]
    ]
    ordered.reverse()
    shot_counts_by_bucket: dict[str, int] = {}
    for item in _shot_events_for_player(player_name):
        bucket = _taipei_week_bucket(item.get("created_at"))
        if bucket:
            shot_counts_by_bucket[bucket] = shot_counts_by_bucket.get(bucket, 0) + 1
    points: list[dict[str, Any]] = []
    for row in ordered:
        bucket = str(row["bucket"] or "")
        week_start = str(row["week_start"] or "")
        week_end = str(row["week_end"] or week_start)
        label = week_start[5:].replace("-", "/") if len(week_start) >= 10 else bucket
        sessions = int(row["sessions"] or 0)
        hours = round(float(row["seconds"] or 0) / 3600, 2)
        points.append({
            "x": label,
            "y": sessions,
            "label": label,
            "week_start_label": week_start,
            "week_end_label": week_end,
            "practice_hours": hours,
            "shot_count": shot_counts_by_bucket.get(bucket, 0),
            "pot_count": sessions,
            "pot_rate": None,
        })
    return points


def _build_mobile_analytics_v1(analytics: dict[str, Any], player_name: str, user: dict[str, Any]) -> dict[str, Any]:
    total_games = int(analytics.get("total_games") or 0)
    total_practice = int(analytics.get("total_practice_sessions") or 0)
    recent_practice_count = len(analytics.get("recent_practice") or [])
    practice_mix = _practice_mix_for_player(player_name)
    practice_overview = _practice_overview_for_player(player_name)
    practice_weekly_points = _practice_weekly_series_for_player(player_name)
    ball_shape_summary = _ball_shape_summary_for_player(player_name)
    offense_summary = _offense_summary_for_player(player_name)
    weekly_shot_count = int(offense_summary["weekly_shot_count"])

    practice_volume = max(total_practice, practice_mix["total"])
    recent_volume = max(recent_practice_count, practice_mix["recent_30"])
    has_real_activity = practice_volume > 0

    accuracy_score = _analytics_score(40 + min(20, practice_mix["accuracy"] * 5) + min(12, recent_volume * 2) + min(8, practice_volume * 0.8))
    cue_control_score = _analytics_score(38 + min(24, practice_mix["pattern"] * 4) + min(14, recent_volume * 2) + min(8, practice_volume * 0.5))
    power_control_score = _analytics_score(40 + min(18, recent_volume * 2.5) + min(12, practice_volume * 0.8) + min(8, practice_mix["single"] * 1.2))
    stroke_stability_score = _analytics_score(42 + min(20, practice_volume * 1.2) + min(12, recent_volume * 2))
    position_play_score = _analytics_score(38 + min(28, practice_mix["pattern"] * 4) + min(10, recent_volume * 1.5))

    if not has_real_activity:
        accuracy_score = 42
        cue_control_score = 38
        power_control_score = 40
        stroke_stability_score = 41
        position_play_score = 37

    ability_scores = [
        {"key": "accuracy", "label": "準度", "score": accuracy_score},
        {"key": "cue_control", "label": "母球控制", "score": cue_control_score},
        {"key": "power_control", "label": "力道控制", "score": power_control_score},
        {"key": "stroke_stability", "label": "出桿穩定", "score": stroke_stability_score},
        {"key": "position_play", "label": "走位能力", "score": position_play_score},
    ]

    score_map = {item["key"]: int(item["score"]) for item in ability_scores}
    overall_score = _analytics_score(
        score_map["accuracy"] * 0.25
        + score_map["cue_control"] * 0.25
        + score_map["power_control"] * 0.15
        + score_map["stroke_stability"] * 0.15
        + score_map["position_play"] * 0.20
    )
    strongest = max(ability_scores, key=lambda item: int(item["score"]))
    weakest = min(ability_scores, key=lambda item: int(item["score"]))

    if overall_score >= 75:
        level_label = "穩定進步中"
    elif overall_score >= 60:
        level_label = "新手進階中"
    elif overall_score >= 45:
        level_label = "基礎建立中"
    else:
        level_label = "剛開始累積資料"

    training_by_weakness = {
        "accuracy": [
            {"title": "直球準度訓練", "reason": "先把瞄準與進球穩定下來", "duration_minutes": 10},
            {"title": "固定角度進球訓練", "reason": "建立不同角度的瞄準感", "duration_minutes": 10},
        ],
        "cue_control": [
            {"title": "定點停球訓練", "reason": "改善母球停位穩定度", "duration_minutes": 10},
            {"title": "短距離母球控制", "reason": "讓母球停在指定區域內", "duration_minutes": 10},
        ],
        "power_control": [
            {"title": "30%、50%、70% 力道控制", "reason": "建立固定出力感", "duration_minutes": 10},
            {"title": "同路線不同力道訓練", "reason": "分辨輕推與中等力道的差異", "duration_minutes": 8},
        ],
        "stroke_stability": [
            {"title": "直球出桿穩定訓練", "reason": "減少出桿左右偏移", "duration_minutes": 10},
            {"title": "慢速出桿節奏練習", "reason": "讓每次出桿節奏更一致", "duration_minutes": 8},
        ],
        "position_play": [
            {"title": "兩球走位訓練", "reason": "練習把母球送到下一球位置", "duration_minutes": 12},
            {"title": "簡單球型清台練習", "reason": "建立進球後下一步的判斷", "duration_minutes": 12},
        ],
    }
    recommended_trainings = training_by_weakness.get(str(weakest["key"]), training_by_weakness["cue_control"])[:2]

    if has_real_activity:
        coach_summary = (
            f"你的{strongest['label']}目前最穩，但{weakest['label']}還需要加強。"
            f"建議本週先練「{recommended_trainings[0]['title']}」，讓進球後的下一步更穩。"
        )
    else:
        coach_summary = "目前資料還少，先累積幾次練習紀錄。建議從定點停球與直球出桿開始，系統會逐步把分析變準。"

    if practice_mix["recent_7"] >= 3:
        trend = {"label": "最近練習量穩定", "summary": "最近 7 天已有多次練習，持續累積會讓能力分數更準。"}
    elif practice_mix["recent_30"] > 0 or recent_practice_count > 0:
        trend = {"label": "最近已有練習紀錄", "summary": "建議維持每週 2 到 3 次短練習，先讓母球控制與力道更穩。"}
    else:
        trend = {"label": "等待更多練習資料", "summary": "完成幾次練習後，這裡會開始顯示進步方向。"}

    return {
        "overall_score": overall_score,
        "level_label": level_label,
        "score_confidence": "medium" if practice_mix["events"] > 0 else "low",
        "score_basis": "根據練習模式紀錄推估，不包含對戰勝負",
        "ability_scores": ability_scores,
        "coach_summary": coach_summary,
        "strongest_ability": str(strongest["label"]),
        "weakest_ability": str(weakest["label"]),
        "recommended_trainings": recommended_trainings,
        "recent_trend": trend,
        "overview": {
            "joined_at": user.get("created_at"),
            "joined_days": _joined_days(user.get("created_at")),
            "total_practice_sessions": practice_overview["total_practice_sessions"],
            "total_battle_matches": practice_overview["total_battle_matches"],
            "overall_score": overall_score,
            "level_label": level_label,
            "score_basis": "根據練習模式紀錄推估，不包含對戰勝負",
        },
        "weekly_summary": {
            "practice_hours": practice_overview["weekly_practice_hours"],
            "shot_count": weekly_shot_count,
            "pot_count": offense_summary["weekly_made_count"],
            "pot_rate": offense_summary["weekly_pot_rate"],
            "shot_data_status": offense_summary["status"],
        },
        "offense_summary": offense_summary,
        "ball_shape_summary": ball_shape_summary,
        "chart_series": {
            "practice_trend": {
                "title": "練習趨勢",
                "x_label": "時間",
                "y_label": "練習次數",
                "status": "ready" if practice_weekly_points else "empty",
                "points": practice_weekly_points,
            },
            "accuracy_trend": {
                "title": "進球準度",
                "x_label": "時間",
                "y_label": "進球率",
                "status": "empty",
                "points": [],
            },
        },
    }


def _mobile_profile_payload(user: dict[str, Any], viewer_user_id: int | None = None) -> dict[str, Any]:
    profile_user = _merge_supabase_mobile_profile(user)
    analytics = _player_analytics(str(user["username"]))
    display_name = str(profile_user.get("display_name") or "").strip() or str(user.get("username") or "").strip()
    follow_counts = _get_follow_counts(int(user["id"]))
    is_private = bool(profile_user.get("is_private") or False)
    is_deactivated = bool(profile_user.get("is_deactivated") or False)
    is_self = viewer_user_id == int(user["id"]) if viewer_user_id is not None else True
    block_state = _get_block_state(viewer_user_id, int(user["id"])) if viewer_user_id is not None else "none"
    is_block_limited = block_state != "none"
    can_view_private = is_self or (
        viewer_user_id is not None
        and is_private
        and _is_following_user(int(viewer_user_id), int(user["id"]))
    )
    is_public_blocked = (is_deactivated and not is_self) or (is_private and not can_view_private) or is_block_limited
    post_count = 0 if is_public_blocked else _count_profile_posts(int(user["id"]), viewer_user_id)
    payload = {
        "user": profile_user,
        "display_name": display_name,
        "bio": "" if is_block_limited else str(profile_user.get("bio") or ""),
        "avatar_url": str(profile_user.get("avatar_url") or ""),
        "player_level": "" if is_public_blocked else _player_level_for_user(profile_user, analytics),
        "followers_count": 0 if is_public_blocked else follow_counts["followers_count"],
        "following_count": 0 if is_public_blocked else follow_counts["following_count"],
        "post_count": post_count,
        "is_private": is_private,
        "is_deactivated": is_deactivated,
        "block_state": block_state,
        "is_blocked_by_me": block_state == "blocked_by_me",
        "has_blocked_me": block_state == "blocked_me",
    }
    if viewer_user_id is not None:
        payload["is_following"] = False if is_block_limited else _is_following_user(viewer_user_id, int(user["id"]))
        payload["is_self"] = is_self
    return payload


def _is_profile_content_blocked(target: dict[str, Any], viewer_user_id: int) -> bool:
    if viewer_user_id == int(target["id"]):
        return False
    profile_user = _merge_supabase_mobile_profile(target)
    if _has_block_between(viewer_user_id, int(target["id"])):
        return True
    if bool(profile_user.get("is_deactivated") or False):
        return True
    if bool(profile_user.get("is_private") or False):
        return not _is_following_user(viewer_user_id, int(target["id"]))
    return False


def _count_profile_posts(user_id: int, viewer_user_id: int | None = None) -> int:
    repo = configured_supabase_post_repository()
    if repo is None:
        return db.count_community_posts_for_user(user_id)
    try:
        _, total = repo.list_posts_for_user(user_id, limit=1, offset=0, viewer_user_id=viewer_user_id)
        return int(total)
    except SupabasePostError as exc:
        print(f"WARNING Supabase profile post count failed; using local post count: {exc}")
        return db.count_community_posts_for_user(user_id)


def _get_follow_counts(user_id: int) -> dict[str, int]:
    repo = configured_supabase_follow_repository()
    if repo is None:
        return db.get_follow_counts(user_id)
    try:
        return repo.follow_counts(user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow count read failed; using local follow counts: {exc}")
        return db.get_follow_counts(user_id)


def _list_follow_refs(user_id: int, kind: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    repo = configured_supabase_follow_repository()
    if repo is None or not hasattr(repo, "list_follow_refs"):
        return db.list_follow_refs(user_id, kind, limit=limit, offset=offset)
    try:
        return repo.list_follow_refs(user_id, kind, limit=limit, offset=offset)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow list read failed; using local follow list: {exc}")
        return db.list_follow_refs(user_id, kind, limit=limit, offset=offset)


def _is_following_user(follower_user_id: int, following_user_id: int) -> bool:
    repo = configured_supabase_follow_repository()
    if repo is None or not hasattr(repo, "is_following"):
        return db.is_following_user(follower_user_id, following_user_id)
    try:
        return repo.is_following(follower_user_id, following_user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow state read failed; using local follow state: {exc}")
        return db.is_following_user(follower_user_id, following_user_id)


def _get_block_state(viewer_user_id: int | None, target_user_id: int) -> str:
    if viewer_user_id is None or int(viewer_user_id) == int(target_user_id):
        return "none"
    repo = configured_supabase_block_repository()
    if repo is None:
        return db.get_block_state(int(viewer_user_id), int(target_user_id))
    try:
        return repo.block_state(int(viewer_user_id), int(target_user_id))
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block state read failed; using local block state: {exc}")
        return db.get_block_state(int(viewer_user_id), int(target_user_id))


def _has_block_between(user_a_id: int, user_b_id: int) -> bool:
    return _get_block_state(user_a_id, user_b_id) != "none"


def _list_block_related_user_ids(user_id: int) -> set[int]:
    repo = configured_supabase_block_repository()
    if repo is None:
        return set(db.list_block_related_user_ids(user_id))
    try:
        return repo.related_user_ids(user_id)
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block related read failed; using local block related users: {exc}")
        return set(db.list_block_related_user_ids(user_id))


def _list_blocked_user_refs(user_id: int) -> list[dict[str, Any]]:
    repo = configured_supabase_block_repository()
    if repo is None:
        return db.list_blocked_user_refs(user_id)
    try:
        return repo.list_blocked_user_refs(user_id)
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block list read failed; using local block list: {exc}")
        return db.list_blocked_user_refs(user_id)


def _remove_follow_between(user_a_id: int, user_b_id: int) -> None:
    follow_repo = configured_supabase_follow_repository()
    if follow_repo is not None:
        try:
            follow_repo.set_follow(user_a_id, user_b_id, False)
            follow_repo.set_follow(user_b_id, user_a_id, False)
        except SupabaseFollowError as exc:
            print(f"WARNING Supabase bilateral follow cleanup failed: {exc}")
    try:
        db.unfollow_user(user_a_id, user_b_id)
        db.unfollow_user(user_b_id, user_a_id)
    except Exception as exc:
        print(f"WARNING local bilateral follow cleanup failed: {exc}")


def _notify_follow_events(actor: dict[str, Any], target: dict[str, Any], was_mutual: bool) -> None:
    actor_id = int(actor["id"])
    target_id = int(target["id"])
    _dispatch_mobile_push_notification(MobilePushEvent(
        recipient_user_id=target_id,
        actor_user_id=actor_id,
        event_type="new_follower",
        source_type="user",
        source_id=actor_id,
        title="有人追蹤你",
        body=f"{_actor_display_name(actor)} 開始追蹤你",
        data={"user_id": actor_id},
    ))
    if was_mutual:
        _dispatch_mobile_push_notification(MobilePushEvent(
            recipient_user_id=target_id,
            actor_user_id=actor_id,
            event_type="mutual_follow",
            source_type="user",
            source_id=actor_id,
            title="你們已互相關注",
            body=f"你和 {_actor_display_name(actor)} 已互相關注",
            data={"user_id": actor_id},
        ))


def _are_mutual_follow_friends(user_a_id: int, user_b_id: int) -> bool:
    if _has_block_between(user_a_id, user_b_id):
        return False
    return _is_following_user(user_a_id, user_b_id) and _is_following_user(user_b_id, user_a_id)


def _ensure_mutual_follow(user_a_id: int, user_b_id: int) -> None:
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(user_a_id, user_b_id, True)
            repo.set_follow(user_b_id, user_a_id, True)
            return
        except SupabaseFollowError as exc:
            print(f"WARNING Supabase mutual follow sync failed; using local follow state: {exc}")
    try:
        db.follow_user(user_a_id, user_b_id)
        db.follow_user(user_b_id, user_a_id)
    except Exception as exc:
        print(f"WARNING local mutual follow sync failed: {exc}")
    _sync_supabase_follow(user_a_id, user_b_id, True)
    _sync_supabase_follow(user_b_id, user_a_id, True)


def _list_mutual_follow_friends(user_id: int) -> list[dict[str, Any]]:
    repo = configured_supabase_follow_repository()
    try:
        refs = repo.list_mutual_friend_refs(user_id) if repo is not None else db.list_mutual_follow_friend_refs(user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase mutual friend read failed; using local mutual friends: {exc}")
        refs = db.list_mutual_follow_friend_refs(user_id)

    friends: list[dict[str, Any]] = []
    for ref in refs:
        if _has_block_between(user_id, int(ref["user_id"])):
            continue
        friend = account_store.get_public_user_by_id(int(ref["user_id"]))
        if friend is None:
            continue
        friend["friendship_created_at"] = str(ref.get("friendship_created_at") or "")
        friends.append(friend)
    return friends


def _friend_user_from_code(code: str) -> dict[str, Any] | None:
    normalized = code.strip()
    if not normalized:
        return None
    if normalized.startswith("@"):
        normalized = normalized[1:].strip()
    if normalized.isdigit():
        return account_store.get_public_user_by_id(int(normalized))
    return account_store.get_public_user_by_username(normalized)


def _validate_local_friend_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if len(normalized) < 2:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_LOCAL_FRIEND", "message": "Local friend name must contain at least 2 characters."},
        )
    if len(normalized) > 32:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_LOCAL_FRIEND", "message": "Local friend name must be 32 characters or fewer."},
        )
    return normalized


FRIEND_MATCH_INVITE_TTL_SECONDS = 10 * 60


def _friend_match_db_path() -> str:
    return str(getattr(db, "db_path", db_path))


def _friend_match_base_url() -> str:
    return str(getattr(config, "MOBILE_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")


def _friend_match_qr_payload(token: str) -> str:
    params = {"token": token}
    base_url = _friend_match_base_url()
    if base_url:
        params["baseUrl"] = base_url
        return f"{base_url}/friend-match?{urlencode(params)}"
    return f"cuevex://friend-match?{urlencode(params)}"


def _mobile_public_base_url() -> str:
    return str(getattr(config, "MOBILE_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")


def _friend_invite_qr_payload(token: str, base_url: str = "") -> str:
    normalized_base_url = (base_url or _mobile_public_base_url()).strip().rstrip("/")
    params = {"token": token}
    if normalized_base_url:
        params["baseUrl"] = normalized_base_url
        return f"{normalized_base_url}/friend-invite?{urlencode(params)}"
    return f"cuevex://friend-invite?{urlencode(params)}"


def _friend_invite_token_from_payload(payload: str) -> str:
    trimmed = payload.strip()
    if not trimmed:
        return ""
    if "?" not in trimmed:
        return trimmed
    params = dict(parse_qsl(trimmed.split("?", 1)[1], keep_blank_values=True))
    return str(params.get("token") or params.get("invite") or "").strip()


def _ensure_friend_match_invite_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS friend_match_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            host_player TEXT NOT NULL,
            game_type TEXT NOT NULL,
            target_rounds INTEGER NOT NULL,
            shot_time_limit INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            guest_user_id INTEGER,
            guest_player TEXT,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            accepted_at INTEGER
        )
        """
    )


def _friend_match_invite_payload(row: sqlite3.Row) -> dict[str, Any]:
    now = int(time.time())
    status = str(row["status"])
    if status == "pending" and int(row["expires_at"]) <= now:
        status = "expired"
    token = str(row["token"])
    return {
        "id": int(row["id"]),
        "token": token,
        "qr_payload": _friend_match_qr_payload(token),
        "host_player": str(row["host_player"]),
        "game_type": str(row["game_type"]),
        "target_rounds": int(row["target_rounds"]),
        "shot_time_limit": int(row["shot_time_limit"]),
        "status": status,
        "guest_user_id": row["guest_user_id"],
        "guest_player": row["guest_player"],
        "created_at": int(row["created_at"]),
        "expires_at": int(row["expires_at"]),
        "accepted_at": row["accepted_at"],
    }


def _friend_match_storage_payload(
    invite: dict[str, Any],
    backend: str,
    warning: str | None = None,
) -> dict[str, Any]:
    payload = dict(invite)
    payload["storage_backend"] = backend
    if warning:
        payload["storage_warning"] = warning
    return payload


def _read_friend_match_invite(token: str) -> dict[str, Any] | None:
    with sqlite3.connect(_friend_match_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_friend_match_invite_table(conn)
        row = conn.execute("SELECT * FROM friend_match_invites WHERE token = ?", (token,)).fetchone()
        if row is None:
            return None
        payload = _friend_match_invite_payload(row)
        if payload["status"] == "expired" and row["status"] == "pending":
            conn.execute("UPDATE friend_match_invites SET status = 'expired' WHERE token = ?", (token,))
        return payload


def _mirror_friend_match_invite_to_sqlite(invite: dict[str, Any]) -> None:
    token = str(invite.get("token") or "").strip()
    if not token:
        return
    with sqlite3.connect(_friend_match_db_path()) as conn:
        _ensure_friend_match_invite_table(conn)
        conn.execute(
            """
            INSERT INTO friend_match_invites (
                token, host_player, game_type, target_rounds, shot_time_limit,
                status, guest_user_id, guest_player, created_at, expires_at, accepted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                host_player = excluded.host_player,
                game_type = excluded.game_type,
                target_rounds = excluded.target_rounds,
                shot_time_limit = excluded.shot_time_limit,
                status = excluded.status,
                guest_user_id = excluded.guest_user_id,
                guest_player = excluded.guest_player,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at,
                accepted_at = excluded.accepted_at
            """,
            (
                token,
                str(invite.get("host_player") or ""),
                str(invite.get("game_type") or "nine_ball"),
                int(invite.get("target_rounds") or 5),
                int(invite.get("shot_time_limit") or 0),
                str(invite.get("status") or "pending"),
                invite.get("guest_user_id"),
                invite.get("guest_player"),
                int(invite.get("created_at") or int(time.time())),
                int(invite.get("expires_at") or int(time.time() + FRIEND_MATCH_INVITE_TTL_SECONDS)),
                invite.get("accepted_at"),
            ),
        )


def _mobile_follow_user_payload(target_user_id: int, viewer_user_id: int, followed_at: str) -> dict[str, Any] | None:
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        return None
    if _has_block_between(viewer_user_id, target_user_id):
        return None
    profile = _mobile_profile_payload(target, viewer_user_id)
    return {
        "user": profile["user"],
        "display_name": profile["display_name"],
        "avatar_url": profile["avatar_url"],
        "player_level": profile["player_level"],
        "is_following": profile.get("is_following", False),
        "is_self": profile.get("is_self", False),
        "followed_at": followed_at,
    }


def _merge_supabase_mobile_profile(user: dict[str, Any]) -> dict[str, Any]:
    repo = configured_supabase_profile_repository()
    if repo is None:
        return user
    try:
        profile = repo.get_profile(int(user["id"]))
    except SupabaseProfileError as exc:
        print(f"WARNING Supabase profile read failed; using local profile: {exc}")
        return user
    if not profile:
        return user
    merged = dict(user)
    merged["display_name"] = str(profile.get("display_name") or user.get("display_name") or "")
    merged["bio"] = str(profile.get("bio") or user.get("bio") or "")
    merged["avatar_url"] = str(profile.get("avatar_url") or user.get("avatar_url") or "")
    merged["is_private"] = bool(profile.get("is_private") or user.get("is_private") or False)
    return merged


def _sync_supabase_mobile_profile(user: dict[str, Any], is_private: bool | None = None, require_success: bool = False) -> None:
    repo = configured_supabase_profile_repository()
    if repo is None:
        return
    try:
        if is_private is not None:
            repo.update_privacy(int(user["id"]), is_private)
            return
        existing_profile = repo.get_profile(int(user["id"])) or {}
        next_display_name = str(user.get("display_name") or "") or str(existing_profile.get("display_name") or "")
        next_bio = str(user.get("bio") or "") or str(existing_profile.get("bio") or "")
        next_avatar_url = str(user.get("avatar_url") or "") or str(existing_profile.get("avatar_url") or "")
        if is_private is None:
            repo.upsert_profile(
                int(user["id"]),
                next_display_name,
                next_bio,
                next_avatar_url,
            )
        else:
            repo.upsert_profile(
                int(user["id"]),
                next_display_name,
                next_bio,
                next_avatar_url,
                is_private,
            )
    except SupabaseProfileError as exc:
        if require_success:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_PROFILE_SYNC_FAILED", "message": str(exc)}) from exc
        print(f"WARNING Supabase profile sync failed; local profile remains active: {exc}")


def _sync_supabase_follow(follower_user_id: int, following_user_id: int, following: bool) -> None:
    repo = configured_supabase_follow_repository()
    if repo is None:
        return
    try:
        repo.set_follow(follower_user_id, following_user_id, following)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow sync failed; local follow state remains active: {exc}")


def _get_profile_posts_from_supabase(
    author_user_id: int,
    limit: int,
    offset: int,
    viewer_user_id: int | None,
) -> tuple[list[dict[str, Any]], int] | None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return None
    try:
        posts, total = repo.list_posts_for_user(
            author_user_id,
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
        )
    except SupabasePostError as exc:
        print(f"WARNING Supabase profile posts read failed; using local posts: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _get_following_feed_from_supabase(
    viewer_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int] | None:
    follow_repo = configured_supabase_follow_repository()
    post_repo = configured_supabase_post_repository()
    if post_repo is None:
        return None
    try:
        if hasattr(post_repo, "list_following_feed"):
            rpc_feed = post_repo.list_following_feed(
                viewer_user_id,
                limit=limit,
                offset=offset,
            )
            if rpc_feed is not None:
                return rpc_feed
        if follow_repo is None:
            return None
        following_user_ids = follow_repo.list_following_user_ids(viewer_user_id)
        blocked_user_ids = _list_block_related_user_ids(viewer_user_id)
        following_user_ids = [user_id for user_id in following_user_ids if user_id not in blocked_user_ids]
        if not following_user_ids:
            return None
        posts, total = post_repo.list_posts_for_users(
            following_user_ids,
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
        )
    except (SupabaseFollowError, SupabasePostError) as exc:
        print(f"WARNING Supabase following feed read failed; using local following feed: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _get_trending_feed_from_supabase(
    viewer_user_id: int,
    limit: int,
    offset: int,
    exclude_ids: list[int],
) -> tuple[list[dict[str, Any]], int] | None:
    post_repo = configured_supabase_post_repository()
    if post_repo is None:
        return None
    try:
        posts, total = post_repo.list_trending_posts(
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
            exclude_ids=exclude_ids,
        )
    except SupabasePostError as exc:
        print(f"WARNING Supabase trending feed read failed; using local trending feed: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _filter_visible_feed_posts(posts: list[dict[str, Any]], viewer_user_id: int) -> list[dict[str, Any]]:
    visible_posts: list[dict[str, Any]] = []
    for post in posts:
        author_user_id = post.get("user_id")
        if author_user_id is None:
            visible_posts.append(post)
            continue
        try:
            author_id = int(author_user_id)
        except (TypeError, ValueError):
            visible_posts.append(post)
            continue
        if author_id == int(viewer_user_id):
            visible_posts.append(post)
            continue
        if _has_block_between(int(viewer_user_id), author_id):
            continue
        try:
            author = account_store.get_public_user_by_id(author_id)
        except SupabaseAccountError as exc:
            print(f"WARNING Supabase feed author read failed; keeping post visible: {exc}")
            visible_posts.append(post)
            continue
        if author is None:
            visible_posts.append(post)
            continue
        merged_author = _merge_supabase_mobile_profile(author)
        if bool(merged_author.get("is_private") or merged_author.get("is_deactivated") or False):
            continue
        visible_posts.append(post)
    return visible_posts


def _parse_exclude_ids(value: str) -> list[int]:
    ids: list[int] = []
    for raw_id in value.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            post_id = int(raw_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_EXCLUDE_IDS", "message": "exclude_ids must be comma-separated integers."},
            ) from exc
        if post_id > 0:
            ids.append(post_id)
    return ids


@router.get("/api/mobile/dashboard")
async def get_mobile_dashboard(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    player_name = str(user["username"])
    analytics = _player_analytics(player_name)
    return {
        "user": user,
        "stats": {
            "total_games": analytics["total_games"],
            "total_wins": analytics["total_wins"],
            "win_rate": analytics["win_rate"],
            "total_practice_sessions": analytics["total_practice_sessions"],
            "total_practice_seconds": analytics.get("total_practice_seconds", 0),
        },
        "recent_games": analytics["recent_games"],
        "recent_practice": analytics["recent_practice"],
        "analytics_v1": _build_mobile_analytics_v1(analytics, player_name, user),
    }


@router.get("/api/mobile/profile")
async def get_mobile_profile(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    return _mobile_profile_payload(user)


@router.patch("/api/mobile/profile")
async def update_mobile_profile(
    request: MobileProfileUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    try:
        updated_user = account_store.update_mobile_profile(
            int(user["id"]),
            display_name=request.display_name,
            bio=request.bio,
            avatar_url=request.avatar_url,
            is_private=request.is_private,
        )
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    if request.is_private is not None:
        updated_user["is_private"] = request.is_private
    _sync_supabase_mobile_profile(updated_user, request.is_private, require_success=request.is_private is not None)
    return _mobile_profile_payload(updated_user)


@router.get("/api/mobile/notifications/settings")
async def get_mobile_notification_settings(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        return repo.get_settings(int(user["id"]))
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.patch("/api/mobile/notifications/settings")
async def update_mobile_notification_settings(
    request: NotificationSettingsUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    updates = request.dict(exclude_none=True)
    try:
        return repo.update_settings(int(user["id"]), updates)
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.post("/api/mobile/notifications/push-token")
async def register_mobile_push_token(
    request: PushTokenRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        token = repo.upsert_push_token(
            int(user["id"]),
            request.expo_push_token,
            device=request.device,
            platform=request.platform,
        )
        return {"status": "registered", "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PUSH_TOKEN", "message": str(exc)}) from exc
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.post("/api/mobile/notifications/test-push")
async def send_mobile_test_push(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    service = configured_mobile_push_notification_service()
    if service is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Supabase notification settings are not configured."},
        )
    result = service.dispatch(MobilePushEvent(
        recipient_user_id=int(user["id"]),
        actor_user_id=int(user["id"]),
        event_type="test_push",
        source_type="diagnostic",
        source_id=int(user["id"]),
        title="CueVex 測試通知",
        body="如果你看到這則通知，代表推播已可送達此裝置。",
        data={"diagnostic": True},
    ))
    return {"status": result.get("status"), "result": result}


@router.get("/api/mobile/notifications/events")
async def get_mobile_notification_events(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    check_receipts: bool = Query(False),
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        events = repo.list_recent_events(int(user["id"]), limit)
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc

    receipt_results: list[dict[str, Any]] = []
    if check_receipts:
        service = configured_mobile_push_notification_service()
        if service is not None:
            for event in events:
                if event.get("status") == "sent" and event.get("expo_ticket_ids"):
                    receipt_results.append(service.check_receipts_for_event(event))
            try:
                events = repo.list_recent_events(int(user["id"]), limit)
            except SupabaseNotificationError:
                pass
    return {"events": events, "receipt_results": receipt_results, "limit": limit}


@router.get("/api/mobile/users/{target_user_id}/profile")
async def get_mobile_public_profile(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    return _mobile_profile_payload(target, int(viewer["id"]))


@router.get("/api/mobile/users/{target_user_id}/posts")
async def get_mobile_public_profile_posts(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if _is_profile_content_blocked(target, int(viewer["id"])):
        return {"posts": [], "total": 0, "limit": limit, "offset": offset}
    supabase_posts = _get_profile_posts_from_supabase(target_user_id, limit, offset, int(viewer["id"]))
    if supabase_posts is None:
        posts, total = db.get_community_posts_for_user(
            target_user_id,
            viewer_user_id=int(viewer["id"]),
            limit=limit,
            offset=offset,
        )
    else:
        posts, total = supabase_posts
    return {"posts": posts, "total": total, "limit": limit, "offset": offset}


@router.get("/api/mobile/users/{target_user_id}/profile-page")
async def get_mobile_public_profile_page(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    is_profile_blocked = _is_profile_content_blocked(target, int(viewer["id"]))
    supabase_posts = None if is_profile_blocked else _get_profile_posts_from_supabase(target_user_id, limit, offset, int(viewer["id"]))
    if supabase_posts is None:
        if is_profile_blocked:
            posts, total = [], 0
        else:
            posts, total = db.get_community_posts_for_user(
                target_user_id,
                viewer_user_id=int(viewer["id"]),
                limit=limit,
                offset=offset,
            )
    else:
        posts, total = supabase_posts
    return {
        "profile": _mobile_profile_payload(target, int(viewer["id"])),
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/mobile/users/{target_user_id}/follows")
async def get_mobile_user_follows(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    kind: str = Query("followers", pattern="^(followers|following)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if _is_profile_content_blocked(target, int(viewer["id"])):
        raise HTTPException(
            status_code=403,
            detail={"code": "PRIVATE_PROFILE", "message": "Follow lists are private for this account."},
        )
    refs, total = _list_follow_refs(target_user_id, kind, limit=limit, offset=offset)
    users: list[dict[str, Any]] = []
    for ref in refs:
        payload = _mobile_follow_user_payload(int(ref["user_id"]), int(viewer["id"]), str(ref.get("followed_at") or ""))
        if payload is not None:
            users.append(payload)
    return {
        "users": users,
        "total": total,
        "limit": limit,
        "offset": offset,
        "kind": kind,
    }


@router.get("/api/mobile/blocks")
async def get_mobile_blocks(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    blocked_users: list[dict[str, Any]] = []
    for ref in _list_blocked_user_refs(int(user["id"])):
        blocked = account_store.get_public_user_by_id(int(ref["user_id"]))
        if blocked is None:
            continue
        profile_payload = _mobile_profile_payload(blocked, int(user["id"]))
        blocked_users.append(
            {
                "user": profile_payload["user"],
                "display_name": profile_payload["display_name"],
                "avatar_url": profile_payload["avatar_url"],
                "blocked_at": str(ref.get("blocked_at") or ""),
            }
        )
    return {"blocked_users": blocked_users, "total": len(blocked_users)}


@router.post("/api/mobile/blocks/{target_user_id}")
async def block_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    if int(user["id"]) == int(target_user_id):
        raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": "Cannot block yourself"})
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    repo = configured_supabase_block_repository()
    if repo is not None:
        try:
            result = repo.block_user(int(user["id"]), target_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": str(exc)}) from exc
        except SupabaseBlockError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_BLOCK_FAILED", "message": str(exc)}) from exc
    else:
        try:
            result = db.block_user(int(user["id"]), target_user_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": str(exc)}) from exc
    _remove_follow_between(int(user["id"]), target_user_id)
    return result


@router.delete("/api/mobile/blocks/{target_user_id}")
async def unblock_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = configured_supabase_block_repository()
    if repo is not None:
        try:
            return repo.unblock_user(int(user["id"]), target_user_id)
        except SupabaseBlockError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_BLOCK_FAILED", "message": str(exc)}) from exc
    return db.unblock_user(int(user["id"]), target_user_id)


@router.post("/api/mobile/follows/{target_user_id}")
async def follow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if int(user["id"]) == target_user_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": "Cannot follow yourself"})
    if _has_block_between(int(user["id"]), target_user_id):
        raise HTTPException(status_code=403, detail={"code": "USER_BLOCKED", "message": "Blocked users cannot follow each other."})
    was_mutual = _is_following_user(target_user_id, int(user["id"]))
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(int(user["id"]), target_user_id, True)
        except SupabaseFollowError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_FOLLOW_FAILED", "message": str(exc)}) from exc
        _notify_follow_events(user, target, was_mutual)
        return {
            "follower_user_id": int(user["id"]),
            "following_user_id": target_user_id,
            "is_following": True,
        }
    try:
        result = db.follow_user(int(user["id"]), target_user_id)
        _sync_supabase_follow(int(user["id"]), target_user_id, True)
        _notify_follow_events(user, target, was_mutual)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": str(exc)}) from exc


@router.delete("/api/mobile/follows/{target_user_id}")
async def unfollow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(int(user["id"]), target_user_id, False)
        except SupabaseFollowError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_FOLLOW_FAILED", "message": str(exc)}) from exc
        return {
            "follower_user_id": int(user["id"]),
            "following_user_id": target_user_id,
            "is_following": False,
        }
    result = db.unfollow_user(int(user["id"]), target_user_id)
    _sync_supabase_follow(int(user["id"]), target_user_id, False)
    return result


@router.get("/api/mobile/feed/following")
async def get_mobile_following_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    user = _current_user(authorization)
    supabase_feed = _get_following_feed_from_supabase(int(user["id"]), limit, offset)
    if supabase_feed is None:
        posts, total = db.get_following_feed_posts(int(user["id"]), limit=limit, offset=offset)
    else:
        posts, total = supabase_feed
    posts = _filter_visible_feed_posts(posts, int(user["id"]))
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMoreFollowing": offset + limit < total,
    }


@router.get("/api/mobile/feed/trending")
async def get_mobile_trending_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    exclude_ids: str = "",
):
    user = _current_user(authorization)
    parsed_exclude_ids = _parse_exclude_ids(exclude_ids)
    supabase_feed = _get_trending_feed_from_supabase(int(user["id"]), limit, offset, parsed_exclude_ids)
    if supabase_feed is None:
        posts, total = db.get_trending_feed_posts(
            int(user["id"]),
            limit=limit,
            offset=offset,
            exclude_ids=parsed_exclude_ids,
        )
    else:
        posts, total = supabase_feed
    posts = _filter_visible_feed_posts(posts, int(user["id"]))
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMoreTrending": offset + limit < total,
    }


@router.get("/api/friends")
async def get_friends(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    return {"friends": _list_mutual_follow_friends(int(user["id"]))}


@router.post("/api/friends/invite-qr")
async def create_friend_invite_qr(
    request: FriendInviteQrCreateRequest = FriendInviteQrCreateRequest(),
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    try:
        invite = account_store.create_friend_invite(int(user["id"]))
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    payload = _friend_invite_qr_payload(str(invite["token"]), request.base_url or "")
    return {
        "token": invite["token"],
        "qr_payload": payload,
        "expires_at": invite["expires_at"],
        "owner": invite["owner"],
    }


@router.post("/api/friends/accept-qr")
async def accept_friend_invite_qr(
    request: FriendInviteQrAcceptRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    invite_token = (request.token or "").strip()
    if not invite_token and request.payload:
        invite_token = _friend_invite_token_from_payload(request.payload)
    if not invite_token:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FRIEND_INVITE", "message": "Friend invite token is required."})
    try:
        result = account_store.accept_friend_invite(int(user["id"]), invite_token)
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    friend = result.get("friend") or {}
    friend_id = int(friend.get("id") or 0)
    if friend_id:
        _ensure_mutual_follow(int(user["id"]), friend_id)
    return {
        "friend": friend,
        "already_friends": bool(result.get("already_friends")),
        "is_following": True,
        "is_mutual": True,
    }


@router.post("/api/friend-match/invites")
async def create_friend_match_invite(request: FriendMatchInviteCreateRequest):
    host_player = _validate_local_friend_name(request.host_player)
    target_rounds = max(1, min(99, int(request.target_rounds or 5)))
    shot_time_limit = max(0, min(600, int(request.shot_time_limit or 0)))
    game_type = str(request.game_type or "nine_ball").strip() or "nine_ball"
    repo = configured_supabase_friend_match_repository()
    supabase_warning: str | None = None
    if repo is not None:
        try:
            invite = repo.create_invite(
                host_player=host_player,
                game_type=game_type,
                target_rounds=target_rounds,
                shot_time_limit=shot_time_limit,
                ttl_seconds=FRIEND_MATCH_INVITE_TTL_SECONDS,
                qr_payload_factory=_friend_match_qr_payload,
            )
            _mirror_friend_match_invite_to_sqlite(invite)
            return _friend_match_storage_payload(invite, "supabase")
        except SupabaseFriendMatchError as exc:
            supabase_warning = str(exc)
            print(f"WARNING Supabase friend match invite create failed; using SQLite fallback: {exc}")

    now = int(time.time())
    expires_at = now + FRIEND_MATCH_INVITE_TTL_SECONDS

    with sqlite3.connect(_friend_match_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_friend_match_invite_table(conn)
        for _ in range(5):
            token = secrets.token_urlsafe(18)
            try:
                conn.execute(
                    """
                    INSERT INTO friend_match_invites (
                        token, host_player, game_type, target_rounds, shot_time_limit, status, created_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (token, host_player, game_type, target_rounds, shot_time_limit, now, expires_at),
                )
                row = conn.execute("SELECT * FROM friend_match_invites WHERE token = ?", (token,)).fetchone()
                if row is not None:
                    backend = "sqlite_fallback" if supabase_warning else "sqlite"
                    return _friend_match_storage_payload(_friend_match_invite_payload(row), backend, supabase_warning)
            except sqlite3.IntegrityError:
                continue

    raise HTTPException(status_code=500, detail={"code": "FRIEND_MATCH_INVITE_FAILED", "message": "Unable to create friend match invite."})


@router.get("/api/friend-match/invites/{token}")
async def get_friend_match_invite(token: str):
    repo = configured_supabase_friend_match_repository()
    supabase_warning: str | None = None
    invite: dict[str, Any] | None = None
    if repo is not None:
        try:
            invite = repo.get_invite(token, _friend_match_qr_payload)
        except SupabaseFriendMatchError as exc:
            supabase_warning = str(exc)
            print(f"WARNING Supabase friend match invite read failed; using SQLite fallback: {exc}")
        if invite is not None:
            _mirror_friend_match_invite_to_sqlite(invite)
            return _friend_match_storage_payload(invite, "supabase")

    if invite is None:
        invite = _read_friend_match_invite(token)
    if invite is None:
        raise HTTPException(status_code=404, detail={"code": "FRIEND_MATCH_INVITE_NOT_FOUND", "message": "Friend match invite not found."})
    backend = "sqlite_fallback" if supabase_warning else "sqlite"
    return _friend_match_storage_payload(invite, backend, supabase_warning)


@router.post("/api/friend-match/invites/{token}/accept")
async def accept_friend_match_invite(token: str, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    now = int(time.time())
    guest_player = str(user.get("username") or _actor_display_name(user)).strip()
    if not guest_player:
        guest_player = _actor_display_name(user)
    repo = configured_supabase_friend_match_repository()
    supabase_warning: str | None = None
    if repo is not None:
        try:
            invite = repo.accept_invite(
                token,
                guest_user_id=int(user["id"]),
                guest_player=guest_player,
                qr_payload_factory=_friend_match_qr_payload,
            )
            _mirror_friend_match_invite_to_sqlite(invite)
            return _friend_match_storage_payload(invite, "supabase")
        except KeyError as exc:
            if _read_friend_match_invite(token) is None:
                raise HTTPException(status_code=404, detail={"code": "FRIEND_MATCH_INVITE_NOT_FOUND", "message": "Friend match invite not found."}) from exc
        except ValueError as exc:
            code = str(exc) or "INVALID_FRIEND_MATCH_INVITE"
            if code == "FRIEND_MATCH_INVITE_EXPIRED":
                raise HTTPException(status_code=400, detail={"code": code, "message": "Friend match invite has expired."}) from exc
            if code == "INVALID_FRIEND":
                raise HTTPException(status_code=400, detail={"code": code, "message": "You cannot join your own friend match invite."}) from exc
            raise HTTPException(status_code=400, detail={"code": code, "message": "Invalid friend match invite."}) from exc
        except SupabaseFriendMatchError as exc:
            supabase_warning = str(exc)
            print(f"WARNING Supabase friend match invite accept failed; using SQLite fallback: {exc}")

    with sqlite3.connect(_friend_match_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_friend_match_invite_table(conn)
        row = conn.execute("SELECT * FROM friend_match_invites WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "FRIEND_MATCH_INVITE_NOT_FOUND", "message": "Friend match invite not found."})
        if str(row["status"]) == "pending" and int(row["expires_at"]) <= now:
            conn.execute("UPDATE friend_match_invites SET status = 'expired' WHERE token = ?", (token,))
            raise HTTPException(status_code=400, detail={"code": "FRIEND_MATCH_INVITE_EXPIRED", "message": "Friend match invite has expired."})
        if str(row["status"]) == "expired":
            raise HTTPException(status_code=400, detail={"code": "FRIEND_MATCH_INVITE_EXPIRED", "message": "Friend match invite has expired."})
        if str(row["host_player"]).strip().casefold() == guest_player.casefold():
            raise HTTPException(status_code=400, detail={"code": "INVALID_FRIEND", "message": "You cannot join your own friend match invite."})
        if str(row["status"]) == "pending":
            conn.execute(
                """
                UPDATE friend_match_invites
                SET status = 'accepted', guest_user_id = ?, guest_player = ?, accepted_at = ?
                WHERE token = ?
                """,
                (int(user["id"]), guest_player, now, token),
            )
        accepted = conn.execute("SELECT * FROM friend_match_invites WHERE token = ?", (token,)).fetchone()
        if accepted is None:
            raise HTTPException(status_code=404, detail={"code": "FRIEND_MATCH_INVITE_NOT_FOUND", "message": "Friend match invite not found."})
        backend = "sqlite_fallback" if supabase_warning else "sqlite"
        return _friend_match_storage_payload(_friend_match_invite_payload(accepted), backend, supabase_warning)


@router.post("/api/friends/{friend_user_id}/start-game")
async def start_friend_game(friend_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    friend = account_store.get_public_user_by_id(friend_user_id)
    if friend is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Friend not found."})
    if not _are_mutual_follow_friends(int(user["id"]), friend_user_id):
        raise HTTPException(status_code=403, detail={"code": "FRIEND_REQUIRED", "message": "You can only start games with friends."})
    if start_friend_game_handler is None:
        raise HTTPException(status_code=503, detail={"code": "GAME_START_UNAVAILABLE", "message": "Game starter is unavailable."})
    return await start_friend_game_handler(str(user["username"]), str(friend["username"]))


@router.post("/api/friends/start-game-by-code")
async def start_friend_game_by_code(request: FriendCodeStartGameRequest, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    friend = _friend_user_from_code(request.code)
    if friend is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Friend code not found."})
    friend_user_id = int(friend["id"])
    if friend_user_id == int(user["id"]):
        raise HTTPException(status_code=400, detail={"code": "INVALID_FRIEND", "message": "You cannot start a friend game with yourself."})
    if not _are_mutual_follow_friends(int(user["id"]), friend_user_id):
        raise HTTPException(status_code=403, detail={"code": "FRIEND_REQUIRED", "message": "You can only start games with friends."})
    if start_friend_game_handler is None:
        raise HTTPException(status_code=503, detail={"code": "GAME_START_UNAVAILABLE", "message": "Game starter is unavailable."})
    return await start_friend_game_handler(str(user["username"]), str(friend["username"]))


@router.post("/api/friends/start-local-game")
async def start_local_friend_game(request: LocalFriendStartGameRequest, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    local_friend_name = _validate_local_friend_name(request.name)
    if local_friend_name.casefold() == str(user["username"]).strip().casefold():
        raise HTTPException(status_code=400, detail={"code": "INVALID_LOCAL_FRIEND", "message": "Local friend name cannot be the same as your username."})
    if start_friend_game_handler is None:
        raise HTTPException(status_code=503, detail={"code": "GAME_START_UNAVAILABLE", "message": "Game starter is unavailable."})
    return await start_friend_game_handler(str(user["username"]), local_friend_name)
