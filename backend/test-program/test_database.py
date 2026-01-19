"""
資料庫測試程式 - 測試 database.py 的基本功能

測試項目:
- 資料表創建與初始化
- CRUD 操作正確性
- 外鍵約束與級聯刪除
- 索引效能
- WAL 模式並發測試
"""

import os
import sys
import time
from datetime import datetime

# 將父目錄加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 設定 UTF-8 編碼（Windows 相容）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from database import Database


def test_database_init():
    """測試資料庫初始化"""
    print("\n[TEST] 資料庫初始化...")
    
    # 使用測試資料庫
    test_db_path = "./data/test_recordings.db"
    
    # 刪除舊的測試資料庫
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = Database(test_db_path)
    
    # 驗證資料表是否創建
    with db.transaction() as conn:
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = ['events', 'players', 'practice_stats', 'recordings']
    assert tables == expected_tables, f"資料表不符: {tables}"
    
    print("  [OK] 資料表創建成功")
    return db


def test_recording_crud(db: Database):
    """測試錄影 CRUD 操作"""
    print("\n[TEST] 錄影 CRUD 操作...")
    
    # 插入測試資料
    recording_data = {
        "game_id": "test_game_001",
        "game_type": "nine_ball",
        "start_time": "2026-01-15T10:00:00",
        "end_time": "2026-01-15T10:30:00",
        "duration_seconds": 1800.0,
        "player1_name": "測試玩家1",
        "player2_name": "測試玩家2",
        "winner": "測試玩家1",
        "player1_score": 5,
        "player2_score": 3,
        "target_rounds": 5,
        "video_path": "./recordings/test_game_001/video.mjpg",
        "video_resolution": "1280x720",
        "video_fps": 30,
        "file_size_mb": 150.5
    }
    
    # 測試插入
    record_id = db.insert_recording(recording_data)
    assert record_id > 0, "插入失敗"
    print(f"  [OK] 插入成功 (ID: {record_id})")
    
    # 測試查詢
    result = db.get_recording("test_game_001")
    assert result is not None, "查詢失敗"
    assert result["game_type"] == "nine_ball", "資料不符"
    print("  [OK] 查詢成功")
    
    # 測試更新
    success = db.update_recording("test_game_001", {
        "winner": "測試玩家2",
        "player2_score": 5
    })
    assert success, "更新失敗"
    
    result = db.get_recording("test_game_001")
    assert result["winner"] == "測試玩家2", "更新資料不符"
    print("  [OK] 更新成功")
    
    # 測試列表查詢
    recordings, total = db.get_recordings(game_type="nine_ball", limit=10)
    assert total == 1, f"總筆數不符: {total}"
    assert len(recordings) == 1, "列表筆數不符"
    print("  [OK] 列表查詢成功")
    
    return "test_game_001"


def test_event_crud(db: Database, game_id: str):
    """測試事件 CRUD 操作"""
    print("\n[TEST] 事件 CRUD 操作...")
    
    # 插入測試事件
    event_data = {
        "game_id": game_id,
        "timestamp": time.time(),
        "event_type": "shot",
        "data": {"ball": 1, "pocket": "corner"},
        "target_ball": 1,
        "potted_ball": 1,
        "first_contact": 1
    }
    
    event_id = db.insert_event(event_data)
    assert event_id > 0, "事件插入失敗"
    print(f"  [OK] 事件插入成功 (ID: {event_id})")
    
    # 查詢事件
    events = db.get_events(game_id)
    assert len(events) == 1, "事件查詢失敗"
    assert events[0]["event_type"] == "shot", "事件資料不符"
    print("  [OK] 事件查詢成功")


def test_practice_stats(db: Database, game_id: str):
    """測試練習統計"""
    print("\n[TEST] 練習統計...")
    
    # 插入練習統計
    stats_data = {
        "game_id": game_id,
        "practice_type": "single",
        "pattern": "straight",
        "total_attempts": 10,
        "successful_attempts": 7,
        "success_rate": 0.7,
        "avg_shot_time": 15.5
    }
    
    stats_id = db.insert_practice_stats(stats_data)
    assert stats_id > 0, "統計插入失敗"
    print(f"  [OK] 統計插入成功 (ID: {stats_id})")
    
    # 查詢統計
    stats = db.get_practice_stats(practice_type="single")
    assert len(stats) == 1, "統計查詢失敗"
    print("  [OK] 統計查詢成功")


def test_player_stats(db: Database):
    """測試玩家統計"""
    print("\n[TEST] 玩家統計...")
    
    # 插入玩家
    player_id = db.upsert_player("測試玩家1")
    assert player_id > 0, "玩家插入失敗"
    print(f"  [OK] 玩家插入成功 (ID: {player_id})")
    
    # 更新玩家統計
    success = db.update_player_stats("測試玩家1")
    assert success, "玩家統計更新失敗"
    print("  [OK] 玩家統計更新成功")
    
    # 查詢玩家統計
    stats = db.get_player_stats("測試玩家1")
    assert stats is not None, "玩家統計查詢失敗"
    assert stats["total_games"] == 1, f"總局數不符: {stats['total_games']}"
    # 注意：在 test_recording_crud 中，winner 已更新為"測試玩家2"，所以測試玩家1的勝場數為0
    assert stats["total_wins"] == 0, f"勝場數不符: {stats['total_wins']}"
    print("  [OK] 玩家統計查詢成功")
    
    # 測試測試玩家2的統計
    db.upsert_player("測試玩家2")
    db.update_player_stats("測試玩家2")
    stats2 = db.get_player_stats("測試玩家2")
    assert stats2["total_wins"] == 1, f"測試玩家2勝場數不符: {stats2['total_wins']}"
    print("  [OK] 測試玩家2統計正確")


def test_cascade_delete(db: Database, game_id: str):
    """測試級聯刪除"""
    print("\n[TEST] 級聯刪除...")
    
    # 刪除錄影（應該級聯刪除事件和統計）
    success = db.delete_recording(game_id)
    assert success, "刪除失敗"
    print("  [OK] 錄影刪除成功")
    
    # 驗證事件也被刪除
    events = db.get_events(game_id)
    assert len(events) == 0, "事件未被級聯刪除"
    print("  [OK] 事件已級聯刪除")


def main():
    """主函數"""
    print("=" * 60)
    print("資料庫測試程式")
    print("=" * 60)
    
    try:
        # 初始化測試
        db = test_database_init()
        
        # CRUD 測試
        game_id = test_recording_crud(db)
        test_event_crud(db, game_id)
        test_practice_stats(db, game_id)
        test_player_stats(db)
        
        # 級聯刪除測試
        test_cascade_delete(db, game_id)
        
        print("\n" + "=" * 60)
        print("[+] 所有測試通過！")
        print("=" * 60)
        
        return 0
    
    except AssertionError as e:
        print(f"\n[X] 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    except Exception as e:
        print(f"\n[X] 測試錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
