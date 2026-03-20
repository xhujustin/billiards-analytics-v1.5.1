"""
相機參數設定功能測試腳本
測試所有 API 端點和影像處理功能
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_get_params():
    """測試獲取相機參數"""
    print_section("測試 1: 獲取相機參數")
    
    try:
        response = requests.get(f"{BASE_URL}/api/camera/params")
        if response.status_code == 200:
            params = response.json()
            print("✓ 成功獲取參數:")
            print(json.dumps(params, indent=2, ensure_ascii=False))
            return params
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return None

def test_update_denoise(enabled=True, strength=30, method="bilateral"):
    """測試更新降噪參數"""
    print_section(f"測試 2: 更新降噪參數 (啟用={enabled}, 強度={strength}, 方法={method})")
    
    try:
        payload = {
            "denoise_enabled": enabled,
            "denoise_strength": strength,
            "denoise_method": method
        }
        response = requests.post(
            f"{BASE_URL}/api/camera/params",
            json=payload
        )
        if response.status_code == 200:
            result = response.json()
            print("✓ 成功更新:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return False

def test_update_exposure(exposure=-5, iso=400):
    """測試更新曝光參數"""
    print_section(f"測試 3: 更新曝光參數 (曝光={exposure}, ISO={iso})")
    
    try:
        payload = {
            "exposure": exposure,
            "iso": iso
        }
        response = requests.post(
            f"{BASE_URL}/api/camera/params",
            json=payload
        )
        if response.status_code == 200:
            result = response.json()
            print("✓ 成功更新:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if result.get("warnings"):
                print("\n⚠ 警告:")
                for warning in result["warnings"]:
                    print(f"  - {warning}")
            return True
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return False

def test_auto_adjust():
    """測試自動調整"""
    print_section("測試 4: 自動調整相機參數")
    
    try:
        response = requests.post(f"{BASE_URL}/api/camera/auto-adjust")
        if response.status_code == 200:
            result = response.json()
            print("✓ 成功啟用自動調整:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return False

def test_get_format():
    """測試獲取格式資訊"""
    print_section("測試 5: 獲取相機格式資訊")
    
    try:
        response = requests.get(f"{BASE_URL}/api/camera/format")
        if response.status_code == 200:
            format_info = response.json()
            print("✓ 成功獲取格式資訊:")
            print(json.dumps(format_info, indent=2, ensure_ascii=False))
            
            if format_info.get("is_compressed"):
                print(f"\n⚠ {format_info.get('warning')}")
                print(f"💡 {format_info.get('recommendation')}")
            else:
                print(f"\n✓ {format_info.get('recommendation')}")
            
            return format_info
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return None

def test_get_stats():
    """測試獲取處理統計"""
    print_section("測試 6: 獲取影像處理統計")
    
    try:
        response = requests.get(f"{BASE_URL}/api/camera/stats")
        if response.status_code == 200:
            stats = response.json()
            print("✓ 成功獲取統計資訊:")
            print(json.dumps(stats, indent=2, ensure_ascii=False))
            
            print(f"\n處理效能:")
            print(f"  - 處理時間: {stats.get('processing_time_ms', 0):.2f} ms")
            print(f"  - 已處理幀數: {stats.get('frame_count', 0)}")
            print(f"  - 平均處理時間: {stats.get('avg_processing_time_ms', 0):.2f} ms")
            
            return stats
        else:
            print(f"✗ 失敗: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return None

def test_denoise_methods():
    """測試不同降噪方法"""
    print_section("測試 7: 測試不同降噪方法")
    
    methods = ["fastNlMeans", "bilateral", "gaussian"]
    results = {}
    
    for method in methods:
        print(f"\n測試方法: {method}")
        test_update_denoise(enabled=True, strength=30, method=method)
        time.sleep(1)  # 等待處理
        
        stats = test_get_stats()
        if stats:
            results[method] = stats.get('processing_time_ms', 0)
            print(f"  處理時間: {results[method]:.2f} ms")
    
    print(f"\n效能比較:")
    for method, time_ms in sorted(results.items(), key=lambda x: x[1]):
        print(f"  {method:15s}: {time_ms:6.2f} ms")
    
    return results

def run_all_tests():
    """執行所有測試"""
    print("\n" + "="*60)
    print("  相機參數設定功能 - 完整測試")
    print("="*60)
    
    # 測試 1: 獲取參數
    params = test_get_params()
    if not params:
        print("\n✗ 無法獲取參數,請確認後端服務是否運行")
        return
    
    time.sleep(0.5)
    
    # 測試 2: 更新降噪
    test_update_denoise(enabled=True, strength=30, method="bilateral")
    time.sleep(0.5)
    
    # 測試 3: 更新曝光
    test_update_exposure(exposure=-5, iso=400)
    time.sleep(0.5)
    
    # 測試 4: 自動調整
    test_auto_adjust()
    time.sleep(0.5)
    
    # 測試 5: 獲取格式
    format_info = test_get_format()
    time.sleep(0.5)
    
    # 測試 6: 獲取統計
    test_get_stats()
    time.sleep(0.5)
    
    # 測試 7: 測試不同降噪方法
    # test_denoise_methods()  # 註解掉以加快測試
    
    print_section("測試完成")
    print("✓ 所有基本測試已完成")
    print("\n建議:")
    print("1. 檢查前端 UI 是否正常顯示")
    print("2. 測試參數調整是否立即生效")
    print("3. 觀察影像品質變化")
    print("4. 監控 FPS 是否受影響")

if __name__ == "__main__":
    run_all_tests()
