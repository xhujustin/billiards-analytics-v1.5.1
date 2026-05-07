import json
from pathlib import Path
from uuid import uuid4

import numpy as np

import roi_manager
from backend.core.coach_semantics import CoachSemanticAdapter, classify_coach_intent


def _config_path() -> Path:
    tmp_dir = Path("tests") / ".tmp_roi_tests"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir / f"{uuid4().hex}.json"


def test_apply_roi_mask_blacks_outside_polygon():
    config_path = _config_path()
    config_path.write_text(
        json.dumps(
            {
                "points": [
                    {"x": 2, "y": 2},
                    {"x": 7, "y": 2},
                    {"x": 7, "y": 7},
                    {"x": 2, "y": 7},
                ]
            }
        ),
        encoding="utf-8",
    )

    frame = np.full((10, 10, 3), 100, dtype=np.uint8)
    masked = roi_manager.apply_roi_mask(frame, config_path)

    assert masked.shape == frame.shape
    assert masked.dtype == frame.dtype
    assert masked[0, 0].tolist() == [0, 0, 0]
    assert masked[5, 5].tolist() == [100, 100, 100]


def test_apply_roi_mask_accepts_list_point_format():
    config_path = _config_path()
    config_path.write_text(json.dumps({"points": [[1, 1], [4, 1], [4, 4], [1, 4]]}), encoding="utf-8")

    frame = np.full((6, 6), 255, dtype=np.uint8)
    masked = roi_manager.apply_roi_mask(frame, config_path)

    assert masked[0, 0] == 0
    assert masked[2, 2] == 255


def test_apply_roi_mask_rejects_invalid_point_count():
    config_path = _config_path()
    config_path.write_text(json.dumps({"points": [[1, 1], [4, 1], [4, 4]]}), encoding="utf-8")

    frame = np.full((6, 6, 3), 255, dtype=np.uint8)

    try:
        roi_manager.apply_roi_mask(frame, config_path)
    except ValueError as exc:
        assert "exactly 4 points" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid ROI point count")


def test_roi_manager_does_not_use_perspective_transform():
    source = Path(roi_manager.__file__).read_text(encoding="utf-8")

    assert "warpPerspective" not in source
    assert "getPerspectiveTransform" not in source


def test_tracking_engine_applies_roi_mask_before_yolo():
    source = Path("backend/tracking/tracking_engine.py").read_text(encoding="utf-8")

    mask_index = source.index("masked_frame = self._apply_configured_roi_mask(frame)")
    predict_index = source.index("results = self.model.predict(")

    assert mask_index < predict_index
    assert "roi_img = masked_frame" in source
    assert "from roi_manager import apply_roi_mask" in source


def test_backend_config_has_roi_mask_defaults():
    source = Path("backend/config.py").read_text(encoding="utf-8")

    assert 'ROI_MASK_ENABLED = get_bool_env("ROI_MASK_ENABLED", "true")' in source
    assert 'ROI_CONFIG_PATH = os.getenv("ROI_CONFIG_PATH"' in source


def test_tracking_engine_is_decoupled_from_ai_coach():
    source = Path("backend/tracking/tracking_engine.py").read_text(encoding="utf-8")

    assert "AICoachManager" not in source
    assert "ai_coach.core.client" not in source
    assert "_update_ai_coach_from_packet" not in source
    assert "get_global_result" not in source


def test_backend_exposes_roi_api_without_perspective_transform():
    source = Path("backend/main.py").read_text(encoding="utf-8")

    assert '@app.get("/api/roi/state")' in source
    assert '@app.post("/api/roi/config")' in source
    assert '@app.post("/api/roi/enabled")' in source
    assert '@app.delete("/api/roi/config")' in source
    assert '"coordinate_space": "original_image"' in source
    assert '"transform": "none"' in source
    assert "warpPerspective" not in source
    assert "getPerspectiveTransform" not in source


def test_settings_page_has_interactive_roi_calibration_ui():
    source = Path("frontend/src/components/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "/api/roi/state" in source
    assert "/api/roi/config" in source
    assert "/api/roi/enabled" in source
    assert "/stream/monitor" in source
    assert "handleRoiImageClick" in source
    assert "naturalWidth" in source
    assert "<svg" in source
    assert "<polygon" in source
    assert "disabled={roiPoints.length !== 4 || isSavingRoi}" in source


def test_backend_metadata_and_chat_expose_ai_coach():
    source = Path("backend/main.py").read_text(encoding="utf-8")

    assert '"ai_coach": ai_coach_payload' in source
    assert '@app.post("/api/coach/chat")' in source
    assert '@app.post("/api/coach/suggest")' in source
    assert '@app.get("/api/coach/state")' in source
    assert "CoachBridge" in source
    assert "Missing 'message' parameter" in source
    assert "coach_bridge.chat(message, context)" in source
    assert "CoachSemanticAdapter" in source
    assert "classify_coach_intent" in source
    assert '"semantic_context": semantic_context' in source
    assert "_submit_ai_coach_analysis" in source
    assert "AI_COACH_AUTO_SUGGESTIONS_ENABLED" in source
    assert 'latest_analysis_data["coach_semantic_snapshot_at"]' in source
    assert "AI_COACH_AUTO_ANALYSIS_INTERVAL_SECONDS" in source
    assert "_semantic_context_signature" in source
    assert "urllib.request.urlopen" not in source
    assert "/api/planner/plan" in source


def test_ai_coach_remote_service_exposes_websocket_contract():
    service = Path("ai_coach/src/ai_coach/service.py").read_text(encoding="utf-8")
    bridge = Path("backend/core/coach_bridge.py").read_text(encoding="utf-8")

    assert '@app.get("/health")' in service
    assert '@app.websocket("/ws/coach")' in service
    assert "analysis.request" in service
    assert "chat.request" in service
    assert "coach.result" in service
    assert "coach.error" in service
    assert "semantic_context" in service
    assert "_normalize_centers" not in service
    assert "ws_ping_interval=AI_COACH_SERVER_WS_PING_INTERVAL" in service
    assert "AI_COACH_VLLM_TIMEOUT_SECONDS" in service
    assert "AI_COACH_MAX_PROMPT_CHARS" in service
    assert "AI_COACH_MAX_TOKENS" in service
    assert "NINE_BALL_COACH_SYSTEM_PROMPT" in service
    assert "is_legal_target=true" in service
    assert "Safety Play" in service
    assert "vLLM HTTP" in service
    assert "_legal_target" in service
    assert "AI_COACH_MAX_TOKENS\", \"80\"" in service
    assert "AI_COACH_MAX_PROMPT_CHARS\", \"900\"" in service
    assert "_clean_recommendation" in service
    assert '"suggestion"' in service
    assert "analysis.request" in bridge
    assert "chat.request" in bridge
    assert "ping_interval=self.ping_interval" in bridge
    assert "request_timeout" in bridge
    assert "_analysis_in_flight" in bridge


def _coach_packet(blocker: bool = False) -> dict:
    balls = [
        {"x": 850, "y": 100, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Yellow", "style": "solid", "number": 1},
    ]
    if blocker:
        balls.append({"x": 520, "y": 280, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Blue", "style": "solid", "number": 2})
    return {
        "white_ball": [180, 460, 40, 40],
        "balls": balls,
        "holes": [[120, 120], [500, 120], [880, 120], [120, 520], [500, 520], [880, 520]],
        "table_roi": [100, 100, 800, 440],
        "status": "analyzing",
    }


def test_coach_semantic_adapter_builds_geometry_tags():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    context = adapter.build_context(_coach_packet())

    assert context["valid"] is True
    assert context["table"]["bounds"]["right"] == 900.0
    ball = context["balls"][0]
    assert ball["center"] == [870.0, 120.0]
    assert ball["bbox_semantics"] == "bbox_xywh_top_left"
    assert "top_right" in ball["semantic_location"]
    assert "top_right" in ball["semantic_location"]
    assert ball["nearest_pocket"]["name"] == "top_right"
    assert "pocket_options" in ball
    assert ball["is_legal_target"] is True
    assert context["rules"]["game"] == "nine_ball"
    assert context["rules"]["legal_target_number"] == 1


def test_coach_semantic_adapter_marks_lowest_number_as_legal_target():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    packet = _coach_packet()
    packet["balls"] = [
        {"x": 850, "y": 100, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Yellow", "style": "solid", "number": 7},
        {"x": 520, "y": 280, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Blue", "style": "solid", "number": 3},
        {"x": 620, "y": 280, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Unknown", "style": "unknown", "number": None},
    ]

    context = adapter.build_context(packet)
    balls = context["balls"]

    assert context["valid"] is True
    assert context["rules"]["legal_target_number"] == 1
    assert [ball["number"] for ball in balls] == [1, 2]
    assert next(ball for ball in balls if ball["number"] == 1)["is_legal_target"] is True
    assert next(ball for ball in balls if ball["number"] == 1)["raw_detected_number"] == 7
    assert next(ball for ball in balls if ball["number"] == 1)["number_source"] == "color_style"
    assert next(ball for ball in balls if ball["number"] == 2)["is_legal_target"] is False


def test_coach_semantic_adapter_treats_orange_unknown_as_possible_one_ball():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    packet = _coach_packet()
    packet["balls"] = [
        {"x": 320, "y": 260, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Orange", "style": "Unknown", "number": None},
        {"x": 700, "y": 200, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Purple", "style": "solid", "number": 4},
    ]

    context = adapter.build_context(packet)
    target = next(ball for ball in context["balls"] if ball["is_legal_target"])

    assert context["valid"] is True
    assert context["rules"]["legal_target_number"] == 1
    assert target["number"] == 1
    assert target["raw_detected_number"] is None
    assert target["number_source"] == "color_style"


def test_coach_semantic_adapter_rejects_unnumbered_object_balls():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    packet = _coach_packet()
    packet["balls"] = [
        {"x": 620, "y": 280, "w": 40, "h": 40, "radius": 20, "conf": 0.9, "color": "Unknown", "style": "unknown", "number": None},
    ]

    context = adapter.build_context(packet)

    assert context["valid"] is False
    assert context["reason"] == "NO_LEGAL_TARGET_BALLS"


def test_coach_semantic_adapter_detects_blockers():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    context = adapter.build_context(_coach_packet(blocker=True))
    target = next(ball for ball in context["balls"] if ball["id"] == "ball-1")

    assert target["cue_path_clear"] is False
    assert any(blocker["id"] == "ball-2" for blocker in target["cue_blocked_by"])


def test_coach_semantic_adapter_stability_and_intent():
    adapter = CoachSemanticAdapter(stable_frames=2, stable_max_shift=10, min_balls=1)
    first = adapter.update(_coach_packet())
    second = adapter.update(_coach_packet())

    assert first["stable"] is False
    assert second["stable"] is True
    assert adapter.state()["stable_ball_count"] == 1
    assert classify_coach_intent("局勢分析") == "table_dependent"
    assert classify_coach_intent("九號球開球洗袋怎麼罰？") == "general_rule"


def test_ai_coach_chat_is_global_sidebar_control():
    dashboard = Path("frontend/src/components/Dashboard.tsx").read_text(encoding="utf-8")
    sidebar = Path("frontend/src/components/Sidebar.tsx").read_text(encoding="utf-8")
    chat = Path("frontend/src/components/AICoachFloatingChat.tsx").read_text(encoding="utf-8")
    stream = Path("frontend/src/components/pages/StreamPage.tsx").read_text(encoding="utf-8")

    assert "AICoachFloatingChat" in dashboard
    assert "AICoachChatWindow" not in dashboard
    assert "isCoachOpen" in dashboard
    assert "coachSessions" in dashboard
    assert "activeCoachSessionId" in dashboard
    assert "sessionId={activeCoachSessionId}" in dashboard
    assert "sessionTitle={activeCoachSession?.title || '對話'}" in dashboard
    assert "onToggleCoach" in sidebar
    assert "sidebar-coach-button" in sidebar
    assert "sidebar-coach-menu" in sidebar
    assert "openCoachMenuSessionId" in sidebar
    assert "onSelectCoachSession" in sidebar
    assert "onRenameCoachSession" in sidebar
    assert "handleDeleteCoachSession" in dashboard
    assert "formatCoachSessionTime" in dashboard
    assert "pageLabels" in dashboard
    assert "event.stopPropagation()" in sidebar
    assert "•••" in sidebar
    assert "重新命名" in sidebar
    assert "/api/coach/chat" in chat
    assert "/api/coach/suggest" in chat
    assert "metadata?.ai_coach" in chat
    assert "messagesBySession" in chat
    assert "suggestion-latest-${currentSessionId}" in chat
    assert "sessionId" in chat
    assert "sessionTitle" in chat
    assert "最小化 AI Coach" in chat
    assert "關閉 AI Coach" in chat
    assert "THINKING_TEXT" in chat
    assert "ai-coach-thinking-dots" in chat
    assert "coach-pending" in chat
    assert "replaceMessage" in chat
    assert "messagesEndRef" in chat
    assert "scrollIntoView" in chat
    assert "{isSending ? THINKING_TEXT : '送出'}" not in chat
    assert "filter(" in chat
    assert "ai-coach-card" not in stream
    assert "/api/coach/chat" not in stream
    assert "plannerView" not in stream


def test_ai_coach_chat_window_component_contract():
    component = Path("frontend/src/components/AICoachChatWindow.tsx").read_text(encoding="utf-8")
    styles = Path("frontend/src/components/AICoachChatWindow.css").read_text(encoding="utf-8")

    assert "AICoachChatWindow" in component
    assert "ChatSession" in component
    assert "ChatMessage" in component
    assert "activeSessionId" in component
    assert "openMenuSessionId" in component
    assert "isMinimized" in component
    assert "isClosed" in component
    assert "sortSessions" in component
    assert "a.isPinned !== b.isPinned" in component
    assert "b.createdAt - a.createdAt" in component
    assert "建立新對話" in component
    assert "最小化" in component
    assert "關閉" in component
    assert "•••" in component
    assert "置頂" in component
    assert "取消置頂" in component
    assert "刪除對話" in component
    assert "event.stopPropagation()" in component
    assert "handleDeleteSession" in component
    assert "createSession(nextIndex)" in component
    assert "onClick={() => setOpenMenuSessionId(null)}" in component
    assert "ai-coach-chat-window__dropdown" in styles
    assert "background: #1f1f1f" in styles
