"""
手動同步錄影到資料庫

這個腳本會掃描 recordings 資料夾中的所有錄影，
如果資料庫中沒有對應記錄，就將其同步到資料庫
"""
import os
import json
import sys
sys.path.append('.')
from database.database import Database

db = Database('./data/recordings.db')
# 使用絕對路徑
recordings_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recordings')

print("開始同步錄影到資料庫...\n")

synced_count = 0
skipped_count = 0
error_count = 0

for game_id in os.listdir(recordings_dir):
    game_dir = os.path.join(recordings_dir, game_id)
    
    if not os.path.isdir(game_dir):
        continue
    
    # 檢查資料庫中是否已存在
    existing = db.get_recording(game_id)
    if existing:
        print(f"[SKIP] {game_id}: 資料庫中已存在")
        skipped_count += 1
        continue
    
    # 讀取 metadata.json
    metadata_path = os.path.join(game_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        print(f"[ERROR] {game_id}: 缺少 metadata.json")
        error_count += 1
        continue
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 準備資料庫記錄
        video_path = os.path.join(game_dir, "video.mp4")
        recording_data = {
            "game_id": metadata["game_id"],
            "game_type": metadata["game_type"],
            "start_time": metadata["start_time"],
            "end_time": metadata.get("end_time"),
            "duration_seconds": metadata.get("duration_seconds", 0),
            "player1_name": metadata.get("players", [None, None])[0] if metadata.get("players") else None,
            "player2_name": metadata.get("players", [None, None])[1] if len(metadata.get("players", [])) > 1 else None,
            "winner": metadata.get("winner"),
            "player1_score": metadata.get("final_score", [0, 0])[0] if metadata.get("final_score") else 0,
            "player2_score": metadata.get("final_score", [0, 0])[1] if len(metadata.get("final_score", [])) > 1 else 0,
            "target_rounds": metadata.get("total_rounds", 0),
            "video_path": video_path,
            "video_resolution": metadata.get("video_resolution", "1280x720"),
            "video_fps": metadata.get("video_fps", 30),
            "file_size_mb": metadata.get("file_size_mb", 0)
        }
        
        db.insert_recording(recording_data)
        print(f"[SYNC] {game_id}: 已同步到資料庫")
        synced_count += 1
        
    except Exception as e:
        print(f"[ERROR] {game_id}: {e}")
        error_count += 1

print(f"\n完成！")
print(f"已同步: {synced_count}")
print(f"已跳過: {skipped_count}")
print(f"錯誤: {error_count}")
