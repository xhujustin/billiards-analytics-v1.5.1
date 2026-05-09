"""
AI Coach 模塊命令行入口點

支持的命令：
    python -m ai_coach --help       查看幫助
    python -m ai_coach --version    查看版本
    python -m ai_coach --info       查看模塊信息
"""

import sys
import argparse
from typing import List, Tuple
from ai_coach import __version__


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        prog="ai_coach",
        description="台球 AI 助教系統",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"AI Coach v{__version__}",
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="顯示模塊信息",
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="運行基本測試",
    )
    
    args = parser.parse_args()
    
    if args.info:
        print_info()
    elif args.test:
        run_test()
    else:
        parser.print_help()


def print_info():
    """打印模塊信息"""
    from ai_coach import (
        StabilityDetector,
        AICoachManager,
        CoordinateSemanticizer,
        CoachPanelRenderer,
    )
    
    print("\n" + "="*60)
    print("🎱 AI Coach 模塊信息")
    print("="*60)
    
    print(f"\n📦 版本：{__version__}")
    
    print("\n📚 主要類別：")
    print(f"  ✓ StabilityDetector - 穩定性檢測")
    print(f"  ✓ CoordinateSemanticizer - 座標語意化")
    print(f"  ✓ AICoachManager - 核心管理器")
    print(f"  ✓ CoachPanelRenderer - 面板渲染器")
    
    print("\n🔧 功能模塊：")
    classes = [
        ("穩定性檢測", StabilityDetector),
        ("座標語意化", CoordinateSemanticizer),
        ("核心管理", AICoachManager),
        ("面板渲染", CoachPanelRenderer),
    ]
    
    for name, cls in classes:
        methods = [m for m in dir(cls) if not m.startswith("_")]
        print(f"  • {name}")
        for method in methods[:3]:
            print(f"    - {method}()")
    
    print("\n📖 詳細文檔：")
    print("  • README.md - 項目介紹")
    print("  • QUICK_REFERENCE.md - API 快速對照")
    print("  • VISUALIZATION_GUIDE.md - 視覺化指南")
    print("  • DEVELOPMENT.md - 開發指南")
    
    print("\n" + "="*60 + "\n")


def run_test():
    """運行基本測試"""
    print("\n🧪 運行 AI Coach 基本測試...\n")
    
    try:
        from ai_coach import StabilityDetector
        
        # 測試 StabilityDetector
        detector = StabilityDetector(
            displacement_threshold=2.0,
            stable_threshold=10,
            cooldown_frames=30,
        )
        
        # 模擬球位
        test_balls: List[Tuple[float, float]] = [(100, 100), (150, 150)]
        result = detector.is_stable(test_balls)
        
        print("✅ StabilityDetector 初始化成功")
        print(f"   穩定性檢測: {result}")
        
        # 測試座標語意化
        from ai_coach import CoordinateSemanticizer
        semanticizer = CoordinateSemanticizer(
            table_width=2800,
            table_height=1400,
        )
        semantic = semanticizer.coordinate_to_semantic(1400, 700)
        print(f"✅ CoordinateSemanticizer 初始化成功")
        print(f"   位置語意: {semantic}")
        
        # 測試管理器
        from ai_coach import AICoachManager
        manager = AICoachManager(
            api_url="http://localhost:8000/api/analyze",
            confidence_threshold=0.5,
        )
        print("✅ AICoachManager 初始化成功")
        
        # 測試面板渲染器
        from ai_coach import CoachPanelRenderer
        renderer = CoachPanelRenderer()
        print("✅ CoachPanelRenderer 初始化成功")
        
        print("\n✨ 所有基本測試通過！\n")
        return 0
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
