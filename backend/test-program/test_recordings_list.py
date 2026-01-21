"""
測試回放 API 是否正確讀取分類資料夾中的錄影
"""
import sys
import os

# 添加 backend 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from recording_manager import RecordingManager

def test_get_recordings_list():
    """測試獲取錄影列表"""
    print("=" * 60)
    print("測試：獲取錄影列表（分類資料夾結構）")
    print("=" * 60)
    
    # 初始化 RecordingManager
    recordings_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'recordings')
    manager = RecordingManager(recordings_dir=recordings_dir)
    
    # 獲取錄影列表
    recordings = manager.get_recordings_list()
    
    print(f"\n找到 {len(recordings)} 個錄影:")
    print("-" * 60)
    
    for i, recording in enumerate(recordings, 1):
        print(f"\n錄影 #{i}:")
        print(f"  Game ID: {recording.get('game_id')}")
        print(f"  遊戲類型: {recording.get('game_type')}")
        print(f"  開始時間: {recording.get('start_time')}")
        print(f"  玩家: {recording.get('players')}")
        print(f"  勝者: {recording.get('winner')}")
        print(f"  時長: {recording.get('duration_seconds'):.2f} 秒")
    
    print("\n" + "=" * 60)
    print(f"✅ 測試完成！共找到 {len(recordings)} 個錄影")
    print("=" * 60)
    
    return len(recordings) > 0

if __name__ == "__main__":
    success = test_get_recordings_list()
    sys.exit(0 if success else 1)
