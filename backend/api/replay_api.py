"""
回放功能 API 模組

提供錄影查詢、統計分析和回放控制 API
符合 v1.5 協議規範
"""

from fastapi import APIRouter, Query, Response, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import os
import cv2

# 導入資料庫
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Database

# 創建 API Router
router = APIRouter()

# 初始化資料庫連線
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
db = Database(db_path)


# ==================== 錄影查詢 API ====================

@router.get("/api/recordings")
async def get_recordings_list(
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
        # 查詢資料庫
        recordings, total = db.get_recordings(
            game_type=game_type,
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
    直接從 recordings 表計算統計，不依賴 players 表
    """
    try:
        # 直接從 recordings 表查詢該玩家的所有錄影
        all_recordings, total_games = db.get_recordings(
            player=player_name,
            limit=10000,  # 獲取所有資料用於統計
            offset=0
        )
        
        # 計算勝場數（只計算 nine_ball 類型的遊戲）
        # 支援平手情況：winner 可能包含多位玩家（逗號分隔）
        nine_ball_games = [r for r in all_recordings if r.get("game_type") == "nine_ball"]
        total_nine_ball_games = len(nine_ball_games)
        total_wins = sum(1 for r in nine_ball_games if player_name in (r.get("winner") or "").split(","))
        win_rate = (total_wins / total_nine_ball_games) if total_nine_ball_games > 0 else 0.0
        
        # 獲取最近比賽（最多5場）
        recent_games = all_recordings[:5]
        
        # 格式化最近比賽
        recent_games_formatted = []
        for game in recent_games:
            # 判斷對手
            if game.get("player1_name") == player_name:
                opponent = game.get("player2_name")
            else:
                opponent = game.get("player1_name")
            
            # 判斷結果（支援平手：winner 包含多位玩家）
            winner = game.get("winner") or ""
            if player_name in winner.split(","):
                # 檢查是否平手（winner 包含多位玩家）
                result = "draw" if "," in winner else "win"
            else:
                result = "loss"
            
            # 格式化比分
            score = f"{game.get('player1_score', 0)}-{game.get('player2_score', 0)}"
            
            recent_games_formatted.append({
                "game_id": game.get("game_id"),
                "opponent": opponent,
                "result": result,
                "score": score,
                "date": game.get("start_time")
            })
        
        # 計算練習統計
        practice_recordings = [r for r in all_recordings if r.get("game_type") in ["practice_single", "practice_pattern"]]
        total_practice_sessions = len(practice_recordings)
        
        # 獲取最近練習記錄（最多5個）
        recent_practice = practice_recordings[:5]
        recent_practice_formatted = [
            {
                "game_id": p.get("game_id"),
                "practice_type": "單球練習" if p.get("game_type") == "practice_single" else "球型練習",
                "duration_seconds": p.get("duration_seconds", 0),
                "date": p.get("start_time")
            }
            for p in recent_practice
        ]
        
        # 返回統計數據（即使沒有記錄也返回初始化數據）
        return JSONResponse({
            "name": player_name,
            "total_games": total_nine_ball_games,
            "total_wins": total_wins,
            "win_rate": round(win_rate, 2),
            "recent_games": recent_games_formatted,
            "total_practice_sessions": total_practice_sessions,
            "recent_practice": recent_practice_formatted
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
        # 查詢時間範圍內的錄影
        recordings, total_games = db.get_recordings(
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # 獲取所有資料用於統計
            offset=0
        )
        
        # 統計練習場次
        practice_recordings = [r for r in recordings if r.get("game_type") in ["practice_single", "practice_pattern"]]
        total_practice_sessions = len(practice_recordings)
        
        # 找出最活躍玩家
        player_counts = {}
        for r in recordings:
            for player in [r.get("player1_name"), r.get("player2_name")]:
                if player:
                    player_counts[player] = player_counts.get(player, 0) + 1
        
        most_active_player = max(player_counts.items(), key=lambda x: x[1])[0] if player_counts else None
        
        # 計算平均遊戲時長
        durations = [r.get("duration_seconds", 0) for r in recordings if r.get("duration_seconds")]
        average_game_duration = sum(durations) / len(durations) if durations else 0.0
        
        # 計算玩家排名列表（只統計 nine_ball 遊戲）
        # 支援平手：winner 可能包含多位玩家（逗號分隔）
        player_stats = {}
        nine_ball_recordings = [r for r in recordings if r.get("game_type") == "nine_ball"]
        
        for r in nine_ball_recordings:
            player1 = r.get("player1_name")
            player2 = r.get("player2_name")
            winner = r.get("winner") or ""
            
            # 統計玩家1
            if player1:
                if player1 not in player_stats:
                    player_stats[player1] = {"total_games": 0, "total_wins": 0}
                player_stats[player1]["total_games"] += 1
                if player1 in winner.split(","):
                    player_stats[player1]["total_wins"] += 1
            
            # 統計玩家2
            if player2:
                if player2 not in player_stats:
                    player_stats[player2] = {"total_games": 0, "total_wins": 0}
                player_stats[player2]["total_games"] += 1
                if player2 in winner.split(","):
                    player_stats[player2]["total_wins"] += 1
        
        # 格式化玩家排名並計算勝率
        player_rankings = []
        for name, stats in player_stats.items():
            total_games = stats["total_games"]
            total_wins = stats["total_wins"]
            win_rate = (total_wins / total_games) if total_games > 0 else 0.0
            
            player_rankings.append({
                "name": name,
                "total_games": total_games,
                "total_wins": total_wins,
                "win_rate": round(win_rate, 2)
            })
        
        # 按總局數排序（從多到少）
        player_rankings.sort(key=lambda x: x["total_games"], reverse=True)
        
        return JSONResponse({
            "period": {
                "start": start_date or "all",
                "end": end_date or "all"
            },
            "total_games": total_games,
            "total_practice_sessions": total_practice_sessions,
            "most_active_player": most_active_player,
            "average_game_duration": round(average_game_duration, 2),
            "player_rankings": player_rankings
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
