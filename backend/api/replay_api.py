"""
回放功能 API 模組

提供錄影查詢、統計分析和回放控制 API
符合 v1.5 協議規範
"""

from fastapi import APIRouter, Query, Response, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, Annotated
import os
import cv2

from fastapi import Body
from core.error_codes import ERR_INTERNAL

# 導入資料庫
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import Database

# 創建 API Router
router = APIRouter()

# 初始化資料庫連線
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
db = Database(db_path)

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
            game_types = ["practice_single", "practice_pattern"]

        # game_type 優先於 mode
        if game_type:
            game_types = None

        recordings, total = db.get_recordings(
            game_type=game_type,
            game_types=game_types,
            player=player,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        return JSONResponse({
            "recordings": recordings,
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
        
        return JSONResponse(recording)
    
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
            event_type=event_type,
            from_time=from_time,
            to_time=to_time
        )
        
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
        
        # 獲取影片路徑
        video_path = recording.get("video_path")
        if not video_path or not os.path.exists(video_path):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Video file not found",
                        "details": {"video_path": video_path}
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
            
            try:
                while True:
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
        
        # 獲取影片路徑
        video_path = recording.get("video_path")
        if not video_path or not os.path.exists(video_path):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "ERR_RECORDING_NOT_FOUND",
                        "message": "Video file not found",
                        "details": {"video_path": video_path}
                    }
                }
            )
        
        # 獲取檔案大小
        file_size = os.path.getsize(video_path)
        
        # 處理範圍請求
        range_header = request.headers.get("range")
        
        if range_header:
            # 解析範圍
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
            
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

