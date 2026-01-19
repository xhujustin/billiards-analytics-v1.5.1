"""
資料遷移工具 - 將現有錄影資料匯入 SQLite 資料庫

功能:
- 掃描 recordings 目錄
- 讀取 metadata.json 和 events.jsonl
- 匯入至 SQLite 資料庫
- 保留原始檔案（向後兼容）
- 錯誤日誌與資料驗證
"""

import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Any

# 設定 UTF-8 編碼（Windows 相容）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from database import Database


class RecordingMigrator:
    """錄影資料遷移器"""
    
    def __init__(self, recordings_dir: str, db_path: str = "./data/recordings.db"):
        """
        初始化遷移器
        
        Args:
            recordings_dir: 錄影目錄路徑
            db_path: 資料庫路徑
        """
        self.recordings_dir = recordings_dir
        self.db = Database(db_path)
        self.errors: List[Dict[str, Any]] = []
        self.success_count = 0
        self.skip_count = 0
    
    def migrate_all(self) -> Dict[str, Any]:
        """
        遷移所有錄影資料
        
        Returns:
            遷移結果統計
        """
        print(f"[*] 開始遷移錄影資料...")
        print(f"[>] 錄影目錄: {self.recordings_dir}")
        print(f"[>] 資料庫: {self.db.db_path}")
        print()
        
        if not os.path.exists(self.recordings_dir):
            print(f"[X] 錄影目錄不存在: {self.recordings_dir}")
            return {
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "error_details": []
            }
        
        # 掃描錄影目錄
        game_dirs = [
            d for d in os.listdir(self.recordings_dir)
            if os.path.isdir(os.path.join(self.recordings_dir, d))
        ]
        
        total = len(game_dirs)
        print(f"[i] 找到 {total} 個錄影目錄\n")
        
        # 逐一遷移
        for idx, game_dir in enumerate(game_dirs, 1):
            game_path = os.path.join(self.recordings_dir, game_dir)
            print(f"[{idx}/{total}] 處理: {game_dir}...", end=" ")
            
            try:
                self._migrate_single(game_path, game_dir)
                print("[OK]")
                self.success_count += 1
            except Exception as e:
                print(f"[FAIL] {str(e)}")
                self.errors.append({
                    "game_dir": game_dir,
                    "error": str(e)
                })
        
        # 輸出結果
        print()
        print("=" * 60)
        print(f"[+] 成功: {self.success_count}")
        print(f"[-] 跳過: {self.skip_count}")
        print(f"[!] 錯誤: {len(self.errors)}")
        print("=" * 60)
        
        if self.errors:
            print("\n錯誤詳情:")
            for err in self.errors:
                print(f"  - {err['game_dir']}: {err['error']}")
        
        return {
            "success": self.success_count,
            "skipped": self.skip_count,
            "errors": len(self.errors),
            "error_details": self.errors
        }
    
    def _migrate_single(self, game_path: str, game_id: str):
        """
        遷移單一錄影
        
        Args:
            game_path: 錄影目錄路徑
            game_id: 遊戲 ID
        """
        # 檢查是否已存在
        existing = self.db.get_recording(game_id)
        if existing:
            self.skip_count += 1
            raise Exception("已存在，跳過")
        
        # 讀取 metadata.json
        metadata_path = os.path.join(game_path, "metadata.json")
        if not os.path.exists(metadata_path):
            raise Exception("metadata.json 不存在")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 準備錄影資料
        recording_data = self._prepare_recording_data(metadata, game_path)
        
        # 插入錄影記錄
        self.db.insert_recording(recording_data)
        
        # 遷移事件日誌
        events_path = os.path.join(game_path, "events.jsonl")
        if os.path.exists(events_path):
            self._migrate_events(events_path, game_id)
        
        # 遷移練習統計（如果是練習模式）
        if metadata.get("game_type") in ["practice_single", "practice_pattern"]:
            self._migrate_practice_stats(metadata, game_id)
        
        # 更新玩家統計
        self._update_player_stats(metadata)
    
    def _prepare_recording_data(self, metadata: Dict[str, Any], game_path: str) -> Dict[str, Any]:
        """
        準備錄影資料
        
        Args:
            metadata: 元資料
            game_path: 錄影目錄路徑
        
        Returns:
            錄影資料字典
        """
        # 解析玩家資訊
        players = metadata.get("players", [])
        player1_name = players[0] if len(players) > 0 else None
        player2_name = players[1] if len(players) > 1 else None
        
        # 解析比分
        final_score = metadata.get("final_score", [0, 0])
        player1_score = final_score[0] if len(final_score) > 0 else 0
        player2_score = final_score[1] if len(final_score) > 1 else 0
        
        # 影片路徑（相對於專案根目錄）
        video_filename = "video.mjpg"
        video_path = os.path.join(game_path, video_filename)
        
        return {
            "game_id": metadata.get("game_id"),
            "game_type": metadata.get("game_type"),
            "start_time": metadata.get("start_time"),
            "end_time": metadata.get("end_time"),
            "duration_seconds": metadata.get("duration_seconds"),
            "player1_name": player1_name,
            "player2_name": player2_name,
            "winner": metadata.get("winner"),
            "player1_score": player1_score,
            "player2_score": player2_score,
            "target_rounds": metadata.get("total_rounds", 0),
            "video_path": video_path,
            "video_resolution": metadata.get("video_resolution"),
            "video_fps": metadata.get("video_fps"),
            "file_size_mb": metadata.get("file_size_mb", 0.0)
        }
    
    def _migrate_events(self, events_path: str, game_id: str):
        """
        遷移事件日誌
        
        Args:
            events_path: events.jsonl 路徑
            game_id: 遊戲 ID
        """
        with open(events_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    event = json.loads(line)
                    
                    event_data = {
                        "game_id": game_id,
                        "timestamp": event.get("timestamp"),
                        "event_type": event.get("event"),
                        "data": event.get("data", {}),
                        "target_ball": None,  # 可從 data 中提取
                        "potted_ball": None,
                        "first_contact": None
                    }
                    
                    # 嘗試從 data 中提取球檯狀態
                    data = event.get("data", {})
                    if isinstance(data, dict):
                        event_data["target_ball"] = data.get("target_ball")
                        event_data["potted_ball"] = data.get("potted_ball")
                        event_data["first_contact"] = data.get("first_contact")
                    
                    self.db.insert_event(event_data)
                
                except json.JSONDecodeError as e:
                    print(f"\n  [!] 事件解析錯誤: {e}")
    
    def _migrate_practice_stats(self, metadata: Dict[str, Any], game_id: str):
        """
        遷移練習統計
        
        Args:
            metadata: 元資料
            game_id: 遊戲 ID
        """
        # 從 metadata 中提取練習統計（如果有）
        # 注意：目前 metadata.json 可能沒有練習統計，需要從 events 計算
        # 這裡先建立基礎記錄
        
        game_type = metadata.get("game_type")
        practice_type = "single" if game_type == "practice_single" else "pattern"
        
        stats_data = {
            "game_id": game_id,
            "practice_type": practice_type,
            "pattern": None,  # 需要從其他地方獲取
            "total_attempts": 0,
            "successful_attempts": 0,
            "success_rate": 0.0,
            "avg_shot_time": None
        }
        
        self.db.insert_practice_stats(stats_data)
    
    def _update_player_stats(self, metadata: Dict[str, Any]):
        """
        更新玩家統計
        
        Args:
            metadata: 元資料
        """
        players = metadata.get("players", [])
        
        for player_name in players:
            if player_name:
                # 確保玩家存在
                self.db.upsert_player(player_name)
                # 更新統計
                self.db.update_player_stats(player_name)


def main():
    """主函數"""
    # 獲取專案根目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # 錄影目錄和資料庫路徑
    recordings_dir = os.path.join(project_root, "recordings")
    db_path = os.path.join(script_dir, "data", "recordings.db")
    
    print("=" * 60)
    print("撞球分析系統 - 資料遷移工具")
    print("=" * 60)
    print()
    
    # 創建遷移器
    migrator = RecordingMigrator(recordings_dir, db_path)
    
    # 執行遷移
    result = migrator.migrate_all()
    
    print()
    print("[+] 遷移完成！")
    print()
    
    # 返回結果
    return result


if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result["errors"] == 0 else 1)
    except Exception as e:
        print(f"\n[X] 遷移失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
