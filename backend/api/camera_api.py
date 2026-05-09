"""
攝像頭控制 API 模組

提供攝像頭列舉和切換功能
改用 PowerShell 列舉設備，避免 OpenCV VCamDShow 錯誤
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
import cv2
import asyncio
import subprocess
import time
import re
from typing import Any, Callable

router = APIRouter()
# 預設燈光情境參數（可透過 API 一鍵切換）
LIGHTING_PROFILES: dict[str, dict[str, Any]] = {
    "warm": {
        "name": "暖光模式",
        "description": "偏暖色溫，降低藍桌面與白光高反差造成的誤判",
        "params": {
            "auto_wb": False,
            "wb_temp": 3600,
            "exposure": -5,
            "brightness": 144,
            "contrast": 130,
            "saturation": 146,
            "sharpness": 128,
            "contrast_adjust": 1.02,
            "brightness_adjust": 12,
            "color_temp_shift": 16,
        }
    },
    "white": {
        "name": "白光模式",
        "description": "偏冷色溫，適合白光環境；若誤判增加可改用暖光模式",
        "params": {
            "auto_wb": False,
            "wb_temp": 6200,
            "exposure": -3,
            "brightness": 152,
            "contrast": 130,
            "saturation": 136,
            "sharpness": 128,
            "contrast_adjust": 1.0,
            "brightness_adjust": 20,
            "color_temp_shift": -16,
        }
    }
}

# Global variables shared from main.py
camera_state: dict[str, Any] | None = None
switch_camera_func: Callable[[Any, Any], Any] | None = None
enumerate_camera_devices_func: Callable[[], list[dict[str, Any]]] | None = None
image_processor = None  # 影像處理器

def init_camera_api(main_module):
    """初始化 API 模組，取得 main 模組的共享變數"""
    global camera_state, switch_camera_func, image_processor, enumerate_camera_devices_func
    camera_state = main_module.camera_state
    switch_camera_func = main_module.switch_camera_background
    image_processor = main_module.image_processor
    enumerate_camera_devices_func = main_module.enumerate_camera_devices


def _get_camera_state() -> dict[str, Any]:
    """取得已由 main.py 注入的相機共享狀態。"""
    if camera_state is None:
        raise HTTPException(status_code=503, detail="Camera API not initialized")
    return camera_state

def get_connected_cameras_windows():
    """
    使用 PowerShell 列舉 Windows 上的攝像頭設備名稱。
    這避免了使用 OpenCV 暴力掃描導致的 VCamDShow 錯誤。
    """
    cameras = []
    try:
        # 使用 PowerShell 獲取 PNPClass 為 Camera 或 Image 的設備
        # 這比 wmic 更可靠，能過濾掉許多虛擬設備
        cmd = [
            "powershell",
            "-Command",
            "Get-PnpDevice -Class Camera,Image -Status OK | Select-Object -ExpandProperty FriendlyName"
        ]
        
        # 執行命令，並強制使用 utf-8 解碼以支援中文名稱
        # 注意：某些 Windows 環境可能需要特定的 codepage (如 'cp950' 或 'mbcs')，
        # 但現代 PowerShell 通常輸出 utf-8 或系統默認編碼。
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        except UnicodeDecodeError:
            # 如果 utf-8 失敗，嘗試系統默認編碼
            result = subprocess.run(cmd, capture_output=True, text=True) # 使用 default locale
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                name = line.strip()
                if name:
                    cameras.append(name)
                    
    except Exception as e:
        print(f"Error enumerating cameras via PowerShell: {e}")
        # 如果失敗，回退到空列表
        return []

    return cameras

@router.get("/api/camera/list")
async def list_cameras():
    """列出可用攝像頭"""
    state = _get_camera_state()
    current_id = state.get("selected_device_id", 0)
    current_backend = state.get("selected_backend", state.get("last_good_backend"))
    available_cameras = []

    enumerator = enumerate_camera_devices_func
    if enumerator:
        try:
            available_cameras = enumerator()
        except Exception as exc:
            print(f"Error probing cameras via OpenCV: {exc}")

    if available_cameras:
        return {
            "cameras": available_cameras,
            "current": current_id,
            "current_backend": current_backend,
            "is_switching": state.get("is_switching", False)
        }
    
    # 1. 獲取系統中的真實攝像頭列表 (不會報錯!)
    camera_names = get_connected_cameras_windows()
    
    # 2. 構建列表
    # 注意: PowerShell 返回的順序通常對應 OpenCV 的 Index 順序
    if camera_names:
        for i, name in enumerate(camera_names):
            available_cameras.append({
                "id": i, 
                "name": f"{name} (Camera {i})" 
            })
    else:
        # 如果 PowerShell 失敗，至少回傳當前使用的和基礎的 0, 1
        available_cameras.append({"id": current_id, "name": f"Camera {current_id} (Data Only)"})
        if current_id != 0:
             available_cameras.append({"id": 0, "name": "Camera 0 (Possible)"})
        if current_id != 1:
             available_cameras.append({"id": 1, "name": "Camera 1 (Possible)"})
        
        available_cameras.sort(key=lambda x: x["id"])

    return {
        "cameras": available_cameras,
        "current": current_id,
        "current_backend": current_backend,
        "is_switching": state.get("is_switching", False)
    }

@router.post("/api/camera/switch")
async def switch_camera(data: dict, background_tasks: BackgroundTasks):
    """切換攝像頭 (非同步)"""
    state = _get_camera_state()
    device_id = data.get("device_id")
    backend = data.get("backend")
    if device_id is None:
        raise HTTPException(status_code=400, detail="Device ID required")
        
    if state.get("is_switching", False):
         raise HTTPException(status_code=400, detail="Camera is currently switching")

    current_backend = state.get("selected_backend", state.get("last_good_backend"))
    if state.get("selected_device_id") == device_id and (backend is None or backend == current_backend):
        return {"status": "ok", "message": "Already on this camera"}

    switcher = switch_camera_func
    if switcher is None:
        raise HTTPException(status_code=503, detail="Camera switcher not available")

    # 標記為正在切換
    state["is_switching"] = True
    
    # 在背景執行切換，避免阻塞 API
    background_tasks.add_task(switcher, device_id, backend)
    
    return {"status": "ok", "message": f"Switching to camera {device_id}..."}


# ==================== 相機參數控制 API ====================

@router.get("/api/camera/params")
async def get_camera_params():
    """獲取當前相機參數"""
    state = _get_camera_state()
    cap = state.get("current_cap")
    if not cap or not cap.isOpened():
        raise HTTPException(status_code=503, detail="Camera not available")
    
    try:
        return {
            # 硬體參數
            "exposure": int(cap.get(cv2.CAP_PROP_EXPOSURE)),
            "iso": int(cap.get(cv2.CAP_PROP_ISO_SPEED)),
            "brightness": int(cap.get(cv2.CAP_PROP_BRIGHTNESS)),
            "contrast": int(cap.get(cv2.CAP_PROP_CONTRAST)),
            "saturation": int(cap.get(cv2.CAP_PROP_SATURATION)),
            "sharpness": int(cap.get(cv2.CAP_PROP_SHARPNESS)),
            "auto_wb": bool(cap.get(cv2.CAP_PROP_AUTO_WB)),
            "wb_temp": int(cap.get(cv2.CAP_PROP_WB_TEMPERATURE)),
            
            # 軟體降噪參數
            "denoise_enabled": image_processor.denoise_enabled if image_processor else False,
            "denoise_strength": image_processor.denoise_strength if image_processor else 0,
            "denoise_method": image_processor.denoise_method if image_processor else "fastNlMeans",
            
            # 影像調整參數
            "brightness_adjust": image_processor.brightness_adjust if image_processor else 0,
            "contrast_adjust": image_processor.contrast_adjust if image_processor else 1.0,
            "color_temp_shift": image_processor.color_temp_shift if image_processor else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取參數失敗: {e}")


@router.post("/api/camera/params")
async def update_camera_params(params: dict):
    """更新相機參數"""
    state = _get_camera_state()
    cap = state.get("current_cap")
    if not cap or not cap.isOpened():
        raise HTTPException(status_code=503, detail="Camera not available")
    
    updated = {}
    warnings = []
    
    try:
        # 更新硬體參數
        exposure_changed = False
        if "exposure" in params:
            success = cap.set(cv2.CAP_PROP_EXPOSURE, params["exposure"])
            if success:
                updated["exposure"] = params["exposure"]
                exposure_changed = True
            else:
                warnings.append("曝光設定可能不支援")
        
        # 如果曝光改變,清空緩衝區並等待相機穩定
        if exposure_changed:
            import time
            time.sleep(0.05)  # 等待50ms讓相機適應新曝光
            # 清空舊的緩衝幀
            for _ in range(5):
                cap.grab()
        
        if "iso" in params:
            success = cap.set(cv2.CAP_PROP_ISO_SPEED, params["iso"])
            if success:
                updated["iso"] = params["iso"]
            else:
                warnings.append("ISO 設定可能不支援")
        
        if "brightness" in params:
            success = cap.set(cv2.CAP_PROP_BRIGHTNESS, params["brightness"])
            if success:
                updated["brightness"] = params["brightness"]
            else:
                warnings.append("亮度設定可能不支援")
        
        if "contrast" in params:
            success = cap.set(cv2.CAP_PROP_CONTRAST, params["contrast"])
            if success:
                updated["contrast"] = params["contrast"]
            else:
                warnings.append("對比度設定可能不支援")
        
        if "saturation" in params:
            success = cap.set(cv2.CAP_PROP_SATURATION, params["saturation"])
            if success:
                updated["saturation"] = params["saturation"]
            else:
                warnings.append("飽和度設定可能不支援")
        
        if "sharpness" in params:
            success = cap.set(cv2.CAP_PROP_SHARPNESS, params["sharpness"])
            if success:
                updated["sharpness"] = params["sharpness"]
            else:
                warnings.append("銳利度設定可能不支援")
        
        if "auto_wb" in params:
            success = cap.set(cv2.CAP_PROP_AUTO_WB, 1 if params["auto_wb"] else 0)
            if success:
                updated["auto_wb"] = params["auto_wb"]
            else:
                warnings.append("自動白平衡設定可能不支援")
        
        if "wb_temp" in params:
            success = cap.set(cv2.CAP_PROP_WB_TEMPERATURE, params["wb_temp"])
            if success:
                updated["wb_temp"] = params["wb_temp"]
            else:
                warnings.append("白平衡色溫設定可能不支援")
        
        # 更新軟體降噪參數
        if image_processor and any(k in params for k in ["denoise_enabled", "denoise_strength", "denoise_method"]):
            image_processor.update_settings(
                enabled=params.get("denoise_enabled"),
                strength=params.get("denoise_strength"),
                method=params.get("denoise_method")
            )
            updated["denoise"] = {
                "enabled": image_processor.denoise_enabled,
                "strength": image_processor.denoise_strength,
                "method": image_processor.denoise_method
            }
        
        # 更新影像調整參數
        if image_processor and any(k in params for k in ["brightness_adjust", "contrast_adjust", "color_temp_shift"]):
            image_processor.update_image_adjustments(
                brightness=params.get("brightness_adjust"),
                contrast=params.get("contrast_adjust"),
                color_temp_shift=params.get("color_temp_shift")
            )
            updated["image_adjust"] = {
                "brightness": image_processor.brightness_adjust,
                "contrast": image_processor.contrast_adjust,
                "color_temp_shift": image_processor.color_temp_shift
            }
        
        return {
            "status": "ok",
            "updated": updated,
            "warnings": warnings if warnings else None
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新參數失敗: {e}")


@router.post("/api/camera/auto-adjust")
async def auto_adjust_camera():
    """自動調整相機參數"""
    state = _get_camera_state()
    cap = state.get("current_cap")
    if not cap or not cap.isOpened():
        raise HTTPException(status_code=503, detail="Camera not available")
    
    try:
        # 啟用自動曝光
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # 0.75 = auto mode
        
        # 啟用自動白平衡
        cap.set(cv2.CAP_PROP_AUTO_WB, 1)
        
        # 等待相機穩定
        import time
        time.sleep(0.1)
        
        # 讀取實際的相機參數 (與 GET /api/camera/params 格式一致)
        actual_params = {
            "exposure": int(cap.get(cv2.CAP_PROP_EXPOSURE)),
            "iso": int(cap.get(cv2.CAP_PROP_ISO_SPEED)),
            "brightness": int(cap.get(cv2.CAP_PROP_BRIGHTNESS)),
            "contrast": int(cap.get(cv2.CAP_PROP_CONTRAST)),
            "saturation": int(cap.get(cv2.CAP_PROP_SATURATION)),
            "sharpness": int(cap.get(cv2.CAP_PROP_SHARPNESS)),
            "auto_wb": True,  # 剛啟用自動白平衡
            "wb_temp": int(cap.get(cv2.CAP_PROP_WB_TEMPERATURE)) if cap.get(cv2.CAP_PROP_WB_TEMPERATURE) > 0 else 4500,
            "denoise_enabled": image_processor.denoise_enabled if image_processor else False,
            "denoise_strength": image_processor.denoise_strength if image_processor else 50,
            "denoise_method": image_processor.denoise_method if image_processor else "bilateral",
            "brightness_adjust": image_processor.brightness_adjust if image_processor else 0,
            "contrast_adjust": image_processor.contrast_adjust if image_processor else 1.0,
            "color_temp_shift": image_processor.color_temp_shift if image_processor else 0
        }
        
        return {
            "status": "ok",
            "message": "Auto-adjustment enabled",
            "adjusted_params": actual_params
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自動調整失敗: {e}")



@router.get("/api/camera/lighting-profiles")
async def get_lighting_profiles():
    """取得可用燈光情境與目前相機關鍵參數"""
    state = _get_camera_state()
    cap = state.get("current_cap")
    if not cap or not cap.isOpened():
        raise HTTPException(status_code=503, detail="Camera not available")

    current = {
        "exposure": int(cap.get(cv2.CAP_PROP_EXPOSURE)),
        "auto_wb": bool(cap.get(cv2.CAP_PROP_AUTO_WB)),
        "wb_temp": int(cap.get(cv2.CAP_PROP_WB_TEMPERATURE)),
    }

    profiles = {}
    for key, cfg in LIGHTING_PROFILES.items():
        profiles[key] = {
            "name": cfg.get("name", key),
            "description": cfg.get("description", ""),
            "params": cfg.get("params", {}),
        }

    return {
        "profiles": profiles,
        "current": current,
        "active_profile": state.get("lighting_profile", "warm"),
    }


@router.post("/api/camera/lighting-profile")
async def apply_lighting_profile(data: dict):
    """套用燈光情境參數（暖光/白光）"""
    state = _get_camera_state()
    profile_name = str(data.get("profile", "")).strip().lower()
    if not profile_name:
        raise HTTPException(status_code=400, detail="Missing profile")

    profile = LIGHTING_PROFILES.get(profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {profile_name}")

    raw_params = profile.get("params", {})
    params = raw_params.copy() if isinstance(raw_params, dict) else {}
    result = await update_camera_params(params)
    state["lighting_profile"] = profile_name
    warnings = result.get("warnings") if isinstance(result, dict) else None
    wb_fallback_active = bool(
        isinstance(warnings, list)
        and any("白平衡色溫設定可能不支援" in w for w in warnings)
        and "color_temp_shift" in params
        and image_processor is not None
    )
    cap = state.get("current_cap")
    effective_current = None
    if cap and cap.isOpened():
        effective_current = {
            "exposure": int(cap.get(cv2.CAP_PROP_EXPOSURE)),
            "auto_wb": bool(cap.get(cv2.CAP_PROP_AUTO_WB)),
            "wb_temp": int(cap.get(cv2.CAP_PROP_WB_TEMPERATURE)),
        }

    return {
        "status": "ok",
        "profile": profile_name,
        "profile_name": profile.get("name", profile_name),
        "message": f"Lighting profile applied: {profile.get('name', profile_name)}",
        "apply_result": result,
        "effective_current": effective_current,
        "wb_fallback_active": wb_fallback_active,
    }

@router.get("/api/camera/format")
async def get_camera_format():
    """獲取當前相機格式資訊"""
    state = _get_camera_state()
    fourcc_info = state.get("fourcc_info", {})
    
    return {
        "format": fourcc_info.get("actual", "UNKNOWN"),
        "description": fourcc_info.get("description", "未知格式"),
        "is_compressed": fourcc_info.get("is_compressed", True),
        "warning": "使用壓縮格式,可能影響影像品質" if fourcc_info.get("is_compressed") else None,
        "recommendation": "建議使用未壓縮格式以獲得最佳品質" if fourcc_info.get("is_compressed") else "當前使用最佳格式"
    }


@router.get("/api/camera/stats")
async def get_processing_stats():
    """獲取影像處理統計資訊"""
    if not image_processor:
        raise HTTPException(status_code=503, detail="Image processor not available")
    
    return image_processor.get_stats()















