"""
回放功能 API 模組

提供錄影查詢、統計分析和回放控制 API
符合 v1.5 協議規範
"""

from fastapi import APIRouter, Query, Response, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, Annotated, Any
from datetime import datetime, timezone
import json
import os
import cv2
import time

from fastapi import Body
from core.error_codes import ERR_INTERNAL

# 導入資料庫
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import Database
from storage.supabase_analytics import SupabaseAnalyticsError, configured_supabase_analytics_repository

# 創建 API Router
router = APIRouter()

# 初始化資料庫連線
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
db = Database(db_path)


def _analytics_repo():
    return configured_supabase_analytics_repository()


def _get_local_recordings(
    game_type: Optional[str],
    game_types: Optional[list[str]],
    player: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    return db.get_recordings(
        game_type=game_type,
        game_types=game_types,
        player=player,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


def _get_recording_with_fallback(game_id: str) -> Optional[dict]:
    """讀取錄影資料，讓影片端點和列表/明細端點使用一致的來源 fallback。"""
    repo = _analytics_repo()
    if repo is not None:
        try:
            recording = repo.get_recording(game_id)
            if recording:
                return recording
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics recording read failed; using SQLite: {exc}")

    return db.get_recording(game_id)


def _parse_datetime_seconds(value: Any) -> Optional[float]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(text.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.timestamp()


def _decode_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value

    try:
        decoded = json.loads(value or "null")
    except (TypeError, json.JSONDecodeError):
        return fallback

    return fallback if decoded is None else decoded


def _get_recording_start_seconds(recording: Optional[dict], game_id: str) -> Optional[float]:
    start_seconds = _parse_datetime_seconds((recording or {}).get("start_time"))
    if start_seconds is not None:
        return start_seconds

    try:
        return datetime.strptime(game_id, "game_%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _get_shot_timeline_events(game_id: str, recording: Optional[dict]) -> list[dict]:
    start_seconds = _get_recording_start_seconds(recording, game_id)

    with db.transaction() as conn:
        cursor = conn.execute(
            """
            SELECT *
            FROM shot_events
            WHERE game_id = ?
            ORDER BY created_at ASC, shot_index ASC, id ASC
            """,
            (game_id,),
        )
        rows = cursor.fetchall()

    events = []
    for row in rows:
        shot = dict(row)
        raw_event = _decode_json(shot.get("raw_event_json"), {})
        potted_balls = _decode_json(shot.get("potted_balls"), [])
        shot_time = _parse_datetime_seconds(
            (raw_event.get("coach_event") or {}).get("timestamp")
            if isinstance(raw_event, dict)
            else None
        )
        if shot_time is None:
            shot_time = _parse_datetime_seconds(shot.get("created_at"))

        offset_seconds = None
        if shot_time is not None and start_seconds is not None:
            offset_seconds = max(0.0, shot_time - start_seconds)

        events.append({
            "id": int(shot.get("id") or 0) + 1_000_000_000,
            "timestamp": shot_time or 0,
            "offset_seconds": offset_seconds,
            "event_type": "shot",
            "source": "shot_events",
            "data": {
                "shot_event_id": shot.get("id"),
                "shot_index": shot.get("shot_index"),
                "mode": shot.get("mode"),
                "target_ball": shot.get("target_ball"),
                "first_contact": shot.get("first_contact"),
                "potted_balls": potted_balls,
                "pocket_result": shot.get("pocket_result"),
                "cue_ball_potted": bool(shot.get("cue_ball_potted")),
                "is_foul": bool(shot.get("is_foul")),
                "foul_reason": shot.get("foul_reason"),
                "difficulty_level": shot.get("difficulty_level"),
                "success_prob": shot.get("success_prob"),
            },
        })

    return events


def _merge_timeline_events(events: list[dict], shot_events: list[dict]) -> list[dict]:
    merged = [*events, *shot_events]
    return sorted(
        merged,
        key=lambda event: (
            event.get("offset_seconds")
            if event.get("offset_seconds") is not None
            else event.get("timestamp") or 0,
            event.get("id") or 0,
        ),
    )


def _find_recording_video_path(game_id: str, recording: Optional[dict]) -> Optional[str]:
    """解析錄影影片位置，支援絕對路徑、專案相對路徑與 recordings 目錄掃描。"""
    candidate_paths = []
    raw_video_path = (recording or {}).get("video_path")

    if raw_video_path:
        candidate_paths.append(str(raw_video_path))
        normalized_raw = os.path.normpath(str(raw_video_path))
        parts = normalized_raw.split(os.sep)
        if "recordings" in parts:
            recordings_index = parts.index("recordings")
            candidate_paths.append(os.path.join(project_root, *parts[recordings_index:]))
        if not os.path.isabs(str(raw_video_path)):
            candidate_paths.append(os.path.join(project_root, str(raw_video_path)))
            candidate_paths.append(os.path.join(os.path.dirname(project_root), str(raw_video_path)))

    for candidate in candidate_paths:
        normalized = os.path.abspath(os.path.normpath(candidate))
        if os.path.isfile(normalized):
            return normalized

    recordings_dir = os.path.join(project_root, "recordings")
    if os.path.isdir(recordings_dir):
        for root, _dirs, files in os.walk(recordings_dir):
            if game_id in root:
                if "video.mp4" in files:
                    return os.path.join(root, "video.mp4")

                mp4_files = [
                    filename for filename in files
                    if filename.lower().endswith(".mp4") and ".tmp." not in filename.lower()
                ]
                if mp4_files:
                    return os.path.join(root, mp4_files[0])

    return None


def _with_video_availability(recording: dict) -> dict:
    enriched = dict(recording)
    video_path = _find_recording_video_path(str(enriched.get("game_id") or ""), enriched)
    enriched["has_video"] = video_path is not None
    if video_path:
        enriched["file_size_mb"] = os.path.getsize(video_path) / (1024 * 1024)
    return enriched


def _recording_not_found_response(game_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "ERR_RECORDING_NOT_FOUND",
                "message": "Recording not found",
                "details": {"game_id": game_id}
            }
        }
    )


def _video_not_found_response(game_id: str, video_path: Optional[str]) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "ERR_RECORDING_VIDEO_NOT_FOUND",
                "message": "Video file not found",
                "details": {"game_id": game_id, "video_path": video_path}
            }
        }
    )

# Global variables shared from main.py
recording_manager = None

def init_replay_api(main_module):
    """初始化 API 模組，取得 main 模組的共享變數"""
    global recording_manager
    recording_manager = main_module.recording_manager


# ==================== 錄影控制 API ====================

@router.post("/api/recording/start")
async def start_recording(request: Annotated[dict, Body(...)]):
    """開始錄影"""
    if recording_manager is None:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": "Recording manager not initialized"}}
        )

    game_type = request.get("game_type")
    players = request.get("players", [])
    
    resolution = request.get("resolution", (1920, 1080)) # Default to 1080p
    
    try:
        game_id = recording_manager.start_recording(
            game_type=game_type,
            players=players,
            resolution=resolution
        )
        return JSONResponse({
            "status": "recording_started",
            "game_id": game_id
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": str(e)}}
        )


@router.post("/api/recording/stop")
async def stop_recording(request: Annotated[dict, Body(...)]):
    """停止錄影"""
    if recording_manager is None:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": "Recording manager not initialized"}}
        )

    final_score = request.get("final_score")
    winner = request.get("winner")
    total_rounds = request.get("total_rounds", 0)
    
    try:
        result = recording_manager.stop_recording(
            final_score=final_score,
            winner=winner,
            total_rounds=total_rounds
        )
        return JSONResponse(result)
    except Exception as e:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": str(e)}}
        )



@router.get("/api/recording/postprocess/{game_id}")
async def get_recording_postprocess_status(game_id: str):
    """查詢錄影後處理狀態（縮圖/轉檔/DB 同步）。"""
    if recording_manager is None:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": "Recording manager not initialized"}}
        )

    try:
        return JSONResponse(recording_manager.get_postprocess_status(game_id))
    except Exception as e:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": str(e)}}
        )
@router.post("/api/recording/event")
async def log_recording_event(request: Annotated[dict, Body(...)]):
    """記錄遊戲事件"""
    if recording_manager is None:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": "Recording manager not initialized"}}
        )

    event_type = request.get("event_type")
    data = request.get("data", {})
    
    try:
        recording_manager.log_event(event_type, data)
        return JSONResponse({"status": "logged"})
    except Exception as e:
         return JSONResponse(
            status_code=500,
            content={"error": {"code": ERR_INTERNAL, "message": str(e)}}
        )


# ==================== 錄影查詢 API ====================

@router.get("/api/recordings")
async def get_recordings_list(
    mode: Optional[str] = Query(None, regex="^(game|practice)$"),
    game_type: Optional[str] = Query(None),
    player: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    獲取錄影列表（支援篩選、分頁）
    
    符合 v1.5 協議規範
    """
    try:
        # mode 轉換為多類型查詢，減少前端全量抓取
        game_types = None
        if mode == "game":
            game_types = ["nine_ball"]
        elif mode == "practice":
            game_types = ["practice_single", "practice_pattern", "practice_accuracy"]

        # game_type 優先於 mode
        if game_type:
            game_types = None

        repo = _analytics_repo()
        if repo is not None:
            try:
                recordings, total = repo.get_recordings(
                    game_type=game_type,
                    game_types=game_types,
                    player=player,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    offset=offset,
                )
                if total == 0 and offset == 0:
                    local_recordings, local_total = _get_local_recordings(
                        game_type=game_type,
                        game_types=game_types,
                        player=player,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                        offset=offset,
                    )
                    if local_total > 0:
                        print("WARNING Supabase analytics recordings empty; using SQLite local recordings")
                        recordings, total = local_recordings, local_total
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics recordings read failed; using SQLite: {exc}")
                recordings, total = _get_local_recordings(
                    game_type=game_type,
                    game_types=game_types,
                    player=player,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    offset=offset
                )
        else:
            recordings, total = _get_local_recordings(
                game_type=game_type,
                game_types=game_types,
                player=player,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
        
        return JSONResponse({
            "recordings": [_with_video_availability(recording) for recording in recordings],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": str(e),
                    "details": {}
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )

@router.get("/api/recordings/{game_id}")
async def get_recording_detail(game_id: str):
    """
    獲取單一錄影詳情
    
    符合 v1.5 協議規範
    """
    try:
        repo = _analytics_repo()
        recording = None
        if repo is not None:
            try:
                recording = repo.get_recording(game_id)
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics recording detail read failed; using SQLite: {exc}")
        if not recording:
            recording = db.get_recording(game_id)
        
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        return JSONResponse(_with_video_availability(recording))
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/recordings/{game_id}/events")
async def get_recording_events(
    game_id: str,
    event_type: Optional[str] = Query(None),
    from_time: Optional[float] = Query(None, alias="from"),
    to_time: Optional[float] = Query(None, alias="to")
):
    """
    獲取錄影事件日誌
    
    符合 v1.5 協議規範
    """
    try:
        # 檢查錄影是否存在
        repo = _analytics_repo()
        recording = None
        if repo is not None:
            try:
                recording = repo.get_recording(game_id)
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics recording read failed; using SQLite: {exc}")
        if not recording:
            recording = db.get_recording(game_id)
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        # 查詢事件
        if repo is not None:
            try:
                events = repo.get_events(
                    game_id=game_id,
                    event_type=event_type,
                    from_time=from_time,
                    to_time=to_time,
                )
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics events read failed; using SQLite: {exc}")
                events = db.get_events(
                    game_id=game_id,
                    event_type=event_type,
                    from_time=from_time,
                    to_time=to_time
                )
        else:
            events = db.get_events(
                game_id=game_id,
                event_type=event_type,
                from_time=from_time,
                to_time=to_time
            )
        
        if event_type in (None, "shot"):
            shot_events = _get_shot_timeline_events(game_id, recording)
            if event_type == "shot":
                events = shot_events
            else:
                events = _merge_timeline_events(events, shot_events)

        return JSONResponse({
            "game_id": game_id,
            "events": events,
            "total": len(events)
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.delete("/api/recordings/{game_id}")
async def delete_recording(game_id: str):
    """
    刪除錄影記錄（級聯刪除相關事件和統計）
    
    符合 v1.5 協議規範
    需要 admin 權限（目前未實作權限檢查）
    """
    try:
        # 檢查錄影是否存在
        recording = db.get_recording(game_id)
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        # 刪除資料庫記錄（級聯刪除）
        success = db.delete_recording(game_id)
        
        if success:
            # 刪除錄影檔案和資料夾
            try:
                import shutil
                recording_dir = os.path.dirname(recording.get("video_path", ""))
                if recording_dir and os.path.exists(recording_dir):
                    shutil.rmtree(recording_dir)
                    print(f"[Recording] Deleted directory: {recording_dir}")
            except Exception as e:
                print(f"[Recording] Failed to delete files: {e}")
            
            return Response(status_code=204)
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "ERR_INTERNAL",
                        "message": "Failed to delete recording",
                        "details": {}
                    }
                }
            )
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


# ==================== 統計分析 API ====================

@router.get("/api/stats/practice")
async def get_practice_stats(
    type: Optional[str] = Query(None),
    pattern: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    獲取練習統計
    
    符合 v1.5 協議規範
    """
    try:
        repo = _analytics_repo()
        if repo is not None:
            try:
                stats = repo.get_practice_stats(
                    practice_type=type,
                    pattern=pattern,
                    start_date=start_date,
                    end_date=end_date,
                )
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics practice stats read failed; using SQLite: {exc}")
                stats = db.get_practice_stats(
                    practice_type=type,
                    pattern=pattern,
                    start_date=start_date,
                    end_date=end_date
                )
        else:
            stats = db.get_practice_stats(
                practice_type=type,
                pattern=pattern,
                start_date=start_date,
                end_date=end_date
            )
        
        # 計算摘要
        total_sessions = len(stats)
        total_attempts = sum(s.get("total_attempts", 0) for s in stats)
        total_successes = sum(s.get("successful_attempts", 0) for s in stats)
        overall_success_rate = (total_successes / total_attempts) if total_attempts > 0 else 0.0
        
        return JSONResponse({
            "stats": stats,
            "summary": {
                "total_sessions": total_sessions,
                "total_attempts": total_attempts,
                "overall_success_rate": round(overall_success_rate, 2)
            }
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/stats/player/{player_name}")
async def get_player_stats(player_name: str):
    """
    獲取玩家統計
    
    符合 v1.5 協議規範
    使用資料庫聚合查詢，避免全量載入 recordings。
    """
    try:
        repo = _analytics_repo()
        if repo is not None:
            try:
                analytics = repo.get_player_analytics(player_name)
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics player stats read failed; using SQLite: {exc}")
                analytics = db.get_player_analytics(player_name)
        else:
            analytics = db.get_player_analytics(player_name)
        return JSONResponse(analytics)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/stats/summary")
async def get_stats_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    獲取統計摘要
    
    符合 v1.5 協議規範
    包含玩家排名列表
    """
    try:
        repo = _analytics_repo()
        if repo is not None:
            try:
                summary = repo.get_stats_summary(
                    start_date=start_date,
                    end_date=end_date,
                )
            except SupabaseAnalyticsError as exc:
                print(f"WARNING Supabase analytics summary read failed; using SQLite: {exc}")
                summary = db.get_stats_summary_aggregated(
                    start_date=start_date,
                    end_date=end_date,
                )
        else:
            summary = db.get_stats_summary_aggregated(
                start_date=start_date,
                end_date=end_date,
            )

        return JSONResponse({
            "period": {
                "start": start_date or "all",
                "end": end_date or "all"
            },
            "total_games": summary["total_games"],
            "total_practice_sessions": summary["total_practice_sessions"],
            "most_active_player": summary["most_active_player"],
            "average_game_duration": summary["average_game_duration"],
            "player_rankings": summary["player_rankings"],
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/diagnostics/analytics-sync")
async def get_analytics_sync_diagnostics():
    """檢查 Supabase analytics schema 與本機待同步佇列。"""
    repo = _analytics_repo()
    supabase_status = {"configured": repo is not None}
    if repo is not None:
        try:
            supabase_status = {"configured": True, **repo.sync_status()}
        except SupabaseAnalyticsError as exc:
            supabase_status = {"configured": True, "ok": False, "error": str(exc)[:500]}

    return JSONResponse({
        "supabase": supabase_status,
        "sqlite_queue": db.get_analytics_sync_queue_status(),
    })


@router.post("/api/diagnostics/analytics-sync/retry")
async def retry_analytics_sync_queue(limit: int = Query(50, ge=1, le=500)):
    """重送本機 SQLite analytics fallback queue 到 Supabase。"""
    result = db.retry_analytics_sync_queue(limit=limit)
    return JSONResponse({
        "retry": result,
        "sqlite_queue": db.get_analytics_sync_queue_status(),
    })


# ==================== 產品化數據頁 API ====================

@router.get("/api/analytics/overview")
async def get_analytics_overview(
    player: Optional[str] = Query(None),
    range: str = Query("today", regex="^(today|week|month|year)$")
):
    """取得數據頁今日總覽、練習紀錄與母球控制摘要。"""
    try:
        return JSONResponse(db.get_analytics_overview(player, range))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/analytics/offense")
async def get_analytics_offense(
    player: Optional[str] = Query(None),
    range: str = Query("today", regex="^(today|week|month|year)$")
):
    """取得距離、難度、厚薄與失誤分布。"""
    try:
        return JSONResponse(db.get_analytics_offense(player, range))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/analytics/trends")
async def get_analytics_trends(
    player: Optional[str] = Query(None),
    bucket: str = Query("day", regex="^(day|week|month|year)$")
):
    """取得日、週、月、年趨勢資料。"""
    try:
        return JSONResponse(db.get_analytics_trends(player, bucket))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


# ==================== 回放控制 API ====================

@router.get("/replay/burnin/{game_id}.mjpg")
async def replay_video_stream(
    game_id: str,
    quality: str = Query("med", regex="^(low|med|high)$")
):
    """
    影片回放串流（MJPEG 格式）
    
    符合 v1.5 P1 Replay 規範
    """
    try:
        # 檢查錄影是否存在
        recording = _get_recording_with_fallback(game_id)
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        # 獲取影片路徑
        video_path = _find_recording_video_path(game_id, recording)
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Video file not found",
                        "details": {"game_id": game_id, "video_path": recording.get("video_path")}
                    }
                }
            )
        
        # 設定畫質參數
        quality_settings = {
            "low": 55,
            "med": 75,
            "high": 85
        }
        jpeg_quality = quality_settings.get(quality, 75)
        
        # 生成 MJPEG 串流
        def generate_mjpeg():
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_delay = 1 / max(1, min(float(fps), 60))
            
            try:
                while True:
                    frame_started_at = time.monotonic()
                    ret, frame = cap.read()
                    if not ret:
                        # 影片結束，重新開始（循環播放）
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    
                    # 編碼為 JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
                    if not ret:
                        continue
                    
                    # 輸出 MJPEG 幀
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                    elapsed = time.monotonic() - frame_started_at
                    if elapsed < frame_delay:
                        time.sleep(frame_delay - elapsed)
            
            finally:
                cap.release()
        
        return StreamingResponse(
            generate_mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/api/recordings/{game_id}/video")
async def get_video_file(game_id: str, request: Request):
    """
    獲取錄影影片檔案（MP4 格式）
    
    支援 HTTP 範圍請求（Range Request）用於影片播放
    """
    try:
        # 檢查錄影是否存在
        recording = _get_recording_with_fallback(game_id)
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        # 獲取影片路徑
        video_path = _find_recording_video_path(game_id, recording)
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Video file not found",
                        "details": {"game_id": game_id, "video_path": recording.get("video_path")}
                    }
                }
            )
        
        # 獲取檔案大小
        file_size = os.path.getsize(video_path)
        
        # 處理範圍請求
        range_header = request.headers.get("range")
        
        if range_header:
            # 解析範圍
            if not range_header.startswith("bytes="):
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

            range_match = range_header.replace("bytes=", "", 1).split("-", 1)
            try:
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
            except ValueError:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

            end = min(end, file_size - 1)
            if file_size <= 0 or start < 0 or start >= file_size or end < start:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
            
            # 讀取指定範圍
            def range_iterator():
                with open(video_path, "rb") as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data
            
            return StreamingResponse(
                range_iterator(),
                status_code=206,
                media_type="video/mp4",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1)
                }
            )
        else:
            # 返回完整影片檔案
            def file_iterator():
                with open(video_path, "rb") as f:
                    yield from f
            
            return StreamingResponse(
                file_iterator(),
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size)
                }
            )
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("/replay/events/{game_id}")
async def replay_events(
    game_id: str,
    from_time: Optional[float] = Query(None, alias="from"),
    to_time: Optional[float] = Query(None, alias="to"),
    downsample: int = Query(1, ge=1),
    format: str = Query("jsonl", regex="^(jsonl|json)$")
):
    """
    事件回放（JSONL 或 JSON 格式）
    
    符合 v1.5 P1 Replay 規範
    """
    try:
        # 檢查錄影是否存在
        recording = db.get_recording(game_id)
        if not recording:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Recording not found",
                        "details": {"game_id": game_id}
                    }
                }
            )
        
        # 查詢事件
        events = db.get_events(
            game_id=game_id,
            from_time=from_time,
            to_time=to_time
        )
        
        # 降採樣
        if downsample > 1:
            events = events[::downsample]
        
        # 根據格式返回
        if format == "jsonl":
            # JSONL 格式（每行一個事件）
            import json
            jsonl_content = "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
            
            return Response(
                content=jsonl_content,
                media_type="application/x-ndjson"
            )
        else:
            # JSON 格式
            return JSONResponse({
                "events": events
            })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR_INTERNAL",
                    "message": str(e),
                    "details": {}
                }
            }
        )

