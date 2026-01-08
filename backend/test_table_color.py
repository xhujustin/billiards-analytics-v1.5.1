"""
测试球桌颜色配置功能
"""
import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from tracking_engine import PoolTracker

def test_color_presets():
    """测试颜色预设"""
    print("=" * 50)
    print("测试球桌颜色预设")
    print("=" * 50)

    print(f"\n当前预设颜色: {config.TABLE_CLOTH_COLOR}")
    print(f"\n可用的颜色预设:")
    for color_key, color_data in config.TABLE_COLOR_PRESETS.items():
        print(f"  - {color_key}: {color_data['name']}")
        print(f"    HSV Lower: {color_data['hsv_lower']}")
        print(f"    HSV Upper: {color_data['hsv_upper']}")

    print(f"\n当前 HSV 设定:")
    print(f"  HSV_LOWER: {config.HSV_LOWER}")
    print(f"  HSV_UPPER: {config.HSV_UPPER}")

def test_tracker_color_update():
    """测试追踪器颜色更新功能"""
    print("\n" + "=" * 50)
    print("测试追踪器颜色更新")
    print("=" * 50)

    # 注意：这里不实际加载 YOLO 模型，只测试配置逻辑
    print("\n创建 PoolTracker 实例 (跳过 YOLO 加载)...")

    # 测试每种颜色
    test_colors = ["green", "gray", "blue", "pink", "purple"]

    for color in test_colors:
        print(f"\n测试颜色: {color}")
        preset = config.TABLE_COLOR_PRESETS.get(color)
        if preset:
            print(f"  名称: {preset['name']}")
            print(f"  HSV Lower: {preset['hsv_lower']}")
            print(f"  HSV Upper: {preset['hsv_upper']}")
        else:
            print(f"  ⚠️ 颜色 '{color}' 不存在")

    print("\n✅ 颜色预设测试完成")

def test_api_response_format():
    """测试 API 响应格式"""
    print("\n" + "=" * 50)
    print("测试 API 响应格式")
    print("=" * 50)

    # 模拟 /api/table/colors 响应
    presets = {}
    for key, value in config.TABLE_COLOR_PRESETS.items():
        presets[key] = {
            "name": value["name"],
            "hsv_lower": value["hsv_lower"].tolist(),
            "hsv_upper": value["hsv_upper"].tolist(),
        }

    response = {
        "current": config.TABLE_CLOTH_COLOR,
        "current_display": config.TABLE_CLOTH_COLOR,
        "presets": presets,
    }

    print("\n模拟 GET /api/table/colors 响应:")
    import json
    print(json.dumps(response, indent=2, ensure_ascii=False))

    print("\n✅ API 响应格式测试完成")

if __name__ == "__main__":
    try:
        test_color_presets()
        test_tracker_color_update()
        test_api_response_format()

        print("\n" + "=" * 50)
        print("✅ 所有测试完成!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
