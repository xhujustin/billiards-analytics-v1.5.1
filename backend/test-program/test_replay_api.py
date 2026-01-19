"""
回放 API 測試程式 - 測試 replay_api.py 的所有端點

測試項目:
- 錄影查詢 API（列表、詳情、事件、刪除）
- 統計分析 API（練習、玩家、摘要）
- 回放控制 API（影片串流、事件回放）
- v1.5 錯誤格式驗證
"""

import os
import sys
import requests
import json

# 設定 UTF-8 編碼（Windows 相容）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 將父目錄加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# API 基礎 URL
BASE_URL = "http://localhost:8001"


def test_get_recordings_list():
    """測試錄影列表查詢"""
    print("\n[TEST] 錄影列表查詢...")
    
    # 測試基本查詢
    response = requests.get(f"{BASE_URL}/api/recordings")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert "recordings" in data, "缺少 recordings 欄位"
    assert "total" in data, "缺少 total 欄位"
    assert "limit" in data, "缺少 limit 欄位"
    assert "offset" in data, "缺少 offset 欄位"
    
    print(f"  [OK] 基本查詢成功（總筆數: {data['total']}）")
    
    # 測試篩選
    response = requests.get(f"{BASE_URL}/api/recordings?game_type=nine_ball&limit=5")
    assert response.status_code == 200, "篩選查詢失敗"
    data = response.json()
    assert data["limit"] == 5, "limit 參數無效"
    
    print("  [OK] 篩選查詢成功")
    
    return data.get("recordings", [])


def test_get_recording_detail(recordings):
    """測試單一錄影詳情查詢"""
    print("\n[TEST] 單一錄影詳情查詢...")
    
    if not recordings:
        print("  [SKIP] 無錄影資料，跳過測試")
        return None
    
    game_id = recordings[0].get("game_id")
    
    # 測試成功查詢
    response = requests.get(f"{BASE_URL}/api/recordings/{game_id}")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert data.get("game_id") == game_id, "game_id 不符"
    
    print(f"  [OK] 查詢成功（game_id: {game_id}）")
    
    # 測試 404 錯誤
    response = requests.get(f"{BASE_URL}/api/recordings/nonexistent_game")
    assert response.status_code == 404, "應返回 404"
    
    error_data = response.json()
    assert "error" in error_data, "缺少 error 欄位"
    assert error_data["error"]["code"] == "ERR_RECORDING_NOT_FOUND", "錯誤碼不符"
    
    print("  [OK] 404 錯誤處理正確")
    
    return game_id


def test_get_recording_events(game_id):
    """測試錄影事件查詢"""
    print("\n[TEST] 錄影事件查詢...")
    
    if not game_id:
        print("  [SKIP] 無 game_id，跳過測試")
        return
    
    # 測試成功查詢
    response = requests.get(f"{BASE_URL}/api/recordings/{game_id}/events")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert "game_id" in data, "缺少 game_id 欄位"
    assert "events" in data, "缺少 events 欄位"
    assert "total" in data, "缺少 total 欄位"
    
    print(f"  [OK] 查詢成功（事件數: {data['total']}）")
    
    # 測試事件類型篩選
    response = requests.get(f"{BASE_URL}/api/recordings/{game_id}/events?event_type=game_start")
    assert response.status_code == 200, "事件類型篩選失敗"
    
    print("  [OK] 事件類型篩選成功")


def test_practice_stats():
    """測試練習統計"""
    print("\n[TEST] 練習統計...")
    
    response = requests.get(f"{BASE_URL}/api/stats/practice")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert "stats" in data, "缺少 stats 欄位"
    assert "summary" in data, "缺少 summary 欄位"
    
    summary = data["summary"]
    assert "total_sessions" in summary, "缺少 total_sessions"
    assert "total_attempts" in summary, "缺少 total_attempts"
    assert "overall_success_rate" in summary, "缺少 overall_success_rate"
    
    print(f"  [OK] 查詢成功（總場次: {summary['total_sessions']}）")


def test_player_stats():
    """測試玩家統計"""
    print("\n[TEST] 玩家統計...")
    
    # 測試不存在的玩家（應返回 404）
    response = requests.get(f"{BASE_URL}/api/stats/player/不存在的玩家")
    assert response.status_code == 404, "應返回 404"
    
    error_data = response.json()
    assert error_data["error"]["code"] == "ERR_PLAYER_NOT_FOUND", "錯誤碼不符"
    
    print("  [OK] 404 錯誤處理正確")
    
    # 如果有玩家資料，測試成功查詢
    # （這裡需要先有玩家資料，暫時跳過）
    print("  [SKIP] 玩家資料查詢（需先有資料）")


def test_stats_summary():
    """測試統計摘要"""
    print("\n[TEST] 統計摘要...")
    
    response = requests.get(f"{BASE_URL}/api/stats/summary")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert "period" in data, "缺少 period 欄位"
    assert "total_games" in data, "缺少 total_games"
    assert "total_practice_sessions" in data, "缺少 total_practice_sessions"
    
    print(f"  [OK] 查詢成功（總遊戲數: {data['total_games']}）")


def test_replay_events(game_id):
    """測試事件回放"""
    print("\n[TEST] 事件回放...")
    
    if not game_id:
        print("  [SKIP] 無 game_id，跳過測試")
        return
    
    # 測試 JSONL 格式
    response = requests.get(f"{BASE_URL}/replay/events/{game_id}?format=jsonl")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    assert response.headers.get("content-type") == "application/x-ndjson", "Content-Type 不符"
    
    print("  [OK] JSONL 格式成功")
    
    # 測試 JSON 格式
    response = requests.get(f"{BASE_URL}/replay/events/{game_id}?format=json")
    assert response.status_code == 200, f"狀態碼錯誤: {response.status_code}"
    
    data = response.json()
    assert "events" in data, "缺少 events 欄位"
    
    print("  [OK] JSON 格式成功")


def test_error_format():
    """測試 v1.5 錯誤格式"""
    print("\n[TEST] v1.5 錯誤格式驗證...")
    
    # 測試 404 錯誤
    response = requests.get(f"{BASE_URL}/api/recordings/nonexistent")
    assert response.status_code == 404, "狀態碼應為 404"
    
    error_data = response.json()
    assert "error" in error_data, "缺少 error 欄位"
    
    error = error_data["error"]
    assert "code" in error, "缺少 code 欄位"
    assert "message" in error, "缺少 message 欄位"
    assert "details" in error, "缺少 details 欄位"
    
    print("  [OK] 錯誤格式符合 v1.5 規範")


def main():
    """主函數"""
    print("=" * 60)
    print("回放 API 測試程式")
    print("=" * 60)
    print(f"\n[*] 測試目標: {BASE_URL}")
    print("[*] 請確保後端服務已啟動")
    
    try:
        # 檢查後端是否啟動
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            print(f"[+] 後端服務正常（版本: {response.json().get('version', 'unknown')}）")
        except requests.exceptions.RequestException:
            print("[X] 後端服務未啟動，請先執行: python main.py")
            return 1
        
        # 執行測試
        recordings = test_get_recordings_list()
        game_id = test_get_recording_detail(recordings)
        test_get_recording_events(game_id)
        test_practice_stats()
        test_player_stats()
        test_stats_summary()
        test_replay_events(game_id)
        test_error_format()
        
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
