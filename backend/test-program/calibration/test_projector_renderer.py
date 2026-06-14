import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from calibration.projector_renderer import ProjectorMode, ProjectorRenderer


def test_practice_empty_status_is_visible_when_no_ar_elements(monkeypatch):
    """practice 模式沒有路線/雷射時仍需顯示淡色狀態，避免投影端看起來斷訊。"""
    import config

    monkeypatch.setattr(config, "PROJECTOR_SHOW_EMPTY_STATUS", True, raising=False)
    renderer = ProjectorRenderer()
    renderer.set_mode(ProjectorMode.PRACTICE)
    renderer.update_ar_data(
        {
            "projector_status": "waiting_for_route",
            "table_polygon": [[100, 100], [1820, 100], [1820, 980], [100, 980]],
            "ar_timestamp": time.time(),
        }
    )

    frame = renderer.render()

    assert frame.max() >= 150
    assert frame.mean() > 10.0


def test_static_ar_elements_return_false_when_nothing_drawn(monkeypatch):
    """空 AR payload 不應被誤判為已繪製，否則 fallback 狀態不會出現。"""
    import config

    monkeypatch.setattr(config, "PROJECTOR_SHOW_EMPTY_STATUS", False, raising=False)
    renderer = ProjectorRenderer()
    renderer.set_mode(ProjectorMode.PRACTICE)
    renderer.update_ar_data({"ar_timestamp": time.time()})

    frame = renderer.render()

    assert frame.max() == 0


def test_manual_planner_route_uses_manual_hold_window(monkeypatch):
    """手動 planner 投影路線不可被 live-yolo 的短 hold 時間提早隱藏。"""
    import config

    now = time.time()
    monkeypatch.setattr(config, "LAST_GOOD_PROJECTOR_AR_HOLD_MS", 1000, raising=False)
    monkeypatch.setattr(config, "PROJECTOR_MANUAL_ROUTE_HOLD_MS", 30000, raising=False)
    monkeypatch.setattr(config, "PROJECTOR_SHOW_EMPTY_STATUS", False, raising=False)
    renderer = ProjectorRenderer()
    renderer.set_mode(ProjectorMode.PRACTICE)
    renderer.update_ar_data(
        {
            "ar_source": "planner_plan",
            "ar_timestamp": now - 5.0,
            "route_segments": [{"type": "cue_to_contact", "points": [[100, 100], [500, 500]]}],
        }
    )

    frame = renderer.render()

    assert frame.max() == 255
