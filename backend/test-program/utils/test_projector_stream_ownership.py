from pathlib import Path


def _function_block(source: str, function_name: str) -> str:
    markers = (f"def {function_name}(", f"async def {function_name}(")
    matched_marker = next(marker for marker in markers if marker in source)
    start = source.index(matched_marker)
    next_def = source.find("\ndef ", start + len(matched_marker))
    next_async_def = source.find("\nasync def ", start + len(matched_marker))
    candidates = [pos for pos in (next_def, next_async_def) if pos != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def test_projector_mjpeg_stream_is_owned_by_projector_render_loop():
    main_py = Path(__file__).resolve().parents[2] / "main.py"
    source = main_py.read_text(encoding="utf-8")

    update_calls = source.count("mjpeg_manager.update_projector(")
    render_loop = _function_block(source, "projector_render_loop")
    legacy_video_ws = _function_block(source, "video_endpoint")

    assert update_calls == 1
    assert "mjpeg_manager.update_projector(" in render_loop
    assert "mjpeg_manager.update_projector(" not in legacy_video_ws


def test_route_projection_publish_replaces_impact_visual_fields():
    main_py = Path(__file__).resolve().parents[2] / "main.py"
    source = main_py.read_text(encoding="utf-8")
    publish_block = _function_block(source, "_publish_route_projection")

    assert '"trajectories": []' in publish_block
    assert '"aim_lines": []' in publish_block
    assert '"ghost_balls": _ghost_balls_from_ar_best_route(ar_best_route)' in publish_block
