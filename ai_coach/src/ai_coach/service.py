from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional

import requests
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


app = FastAPI(title="AI Coach Remote WebSocket Service")


def _optional_float_env(name: str, default: str = "0") -> Optional[float]:
    """Return a positive float from env, or None when WebSocket ping is disabled."""
    value = os.getenv(name, default).strip()
    try:
        parsed = float(value)
    except ValueError:
        return None
    return None if parsed <= 0 else parsed


AI_COACH_HOST = os.getenv("AI_COACH_HOST", "0.0.0.0")
AI_COACH_PORT = int(os.getenv("AI_COACH_PORT", "8010"))
AI_COACH_API_URL = os.getenv("AI_COACH_API_URL", "http://localhost:8002/v1/chat/completions")
AI_COACH_MODEL = os.getenv("AI_COACH_MODEL", "/home/lucian039/gemma-4-awq")
AI_COACH_VLLM_TIMEOUT_SECONDS = float(os.getenv("AI_COACH_VLLM_TIMEOUT_SECONDS", "90"))
AI_COACH_MAX_TOKENS = int(os.getenv("AI_COACH_MAX_TOKENS", "80"))
AI_COACH_MAX_PROMPT_CHARS = int(os.getenv("AI_COACH_MAX_PROMPT_CHARS", "900"))
AI_COACH_SERVER_WS_PING_INTERVAL = _optional_float_env("AI_COACH_SERVER_WS_PING_INTERVAL", "0")
AI_COACH_SERVER_WS_PING_TIMEOUT = _optional_float_env("AI_COACH_SERVER_WS_PING_TIMEOUT", "0")


NINE_BALL_COACH_SYSTEM_PROMPT = (
    "你是九號球AI Coach。只用JSON中is_legal_target=true的球當唯一合法目標。"
    "若該球cue_path_clear與nearest_pocket.path_clear皆為true，給進攻與走位建議。"
    "若任一為false，嚴禁改打其他號碼，必須建議Safety Play防守或解球。"
    "若無合法目標資訊，要求重新辨識。繁中回答，80字內。"
)


def _short_json(value: Any, limit: int = 240) -> str:
    """Serialize compact JSON for prompts with a hard character limit."""
    if value in (None, "", [], {}):
        return "無"
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else f"{text[:limit]}..."


def _legal_target(balls: Any) -> Optional[dict[str, Any]]:
    """Return the single legal target marked by CoachSemanticAdapter."""
    if not isinstance(balls, list):
        return None
    for ball in balls:
        if isinstance(ball, dict) and ball.get("is_legal_target") is True:
            return ball
    return None


def _compact_legal_target_summary(semantic_context: dict[str, Any]) -> str:
    """Summarize only the legal target to stay under Gemma's 1024 token limit."""
    ball = _legal_target(semantic_context.get("balls"))
    if not ball:
        return "legal_target=missing"

    nearest = ball.get("nearest_pocket") if isinstance(ball.get("nearest_pocket"), dict) else {}
    blocked_by = nearest.get("blocked_by") or ball.get("cue_blocked_by") or []
    fields = {
        "id": ball.get("id"),
        "number": ball.get("number"),
        "center": ball.get("center"),
        "semantic_location": ball.get("semantic_location"),
        "cue_path_clear": ball.get("cue_path_clear"),
        "nearest_pocket": {
            "name": nearest.get("name"),
            "distance_px": nearest.get("distance_px"),
            "path_clear": nearest.get("path_clear"),
            "blocked_by": blocked_by[:3] if isinstance(blocked_by, list) else blocked_by,
        },
    }
    return _short_json(fields, limit=420)


def _compact_rules_summary(semantic_context: dict[str, Any]) -> str:
    """Summarize nine-ball rule fields from semantic context."""
    rules = semantic_context.get("rules") if isinstance(semantic_context.get("rules"), dict) else {}
    return _short_json(
        {
            "game": rules.get("game", "nine_ball"),
            "legal_target_number": rules.get("legal_target_number"),
            "legal_target_id": rules.get("legal_target_id"),
        },
        limit=160,
    )


def _summarize_multi_plan(raw_multi_plan: Any) -> str:
    """Keep only the route-planner target fields useful to the LLM."""
    if not isinstance(raw_multi_plan, dict):
        return "無"
    best = raw_multi_plan.get("best_route") or raw_multi_plan.get("best") or raw_multi_plan
    if not isinstance(best, dict):
        return "無"
    return _short_json(
        {
            "route_type": best.get("route_type"),
            "target_ball_number": best.get("target_ball_number"),
            "success_prob": best.get("success_prob"),
            "difficulty_level": best.get("difficulty_level"),
            "risk_flags": best.get("risk_flags"),
        },
        limit=220,
    )


def _semantic_description(semantic_context: dict[str, Any]) -> str:
    """Create a concise semantic summary from backend geometry results."""
    if not semantic_context.get("valid"):
        reason = semantic_context.get("reason") or semantic_context.get("unstable_reason") or "UNKNOWN"
        return f"無有效檯面語意資料，原因：{reason}"

    legal = _legal_target(semantic_context.get("balls"))
    if not legal:
        return "缺少合法目標球資訊"

    nearest = legal.get("nearest_pocket") if isinstance(legal.get("nearest_pocket"), dict) else {}
    return (
        f"合法目標{legal.get('number')}號；"
        f"cue_path={legal.get('cue_path_clear')}；"
        f"pocket={nearest.get('name')}；"
        f"pocket_path={nearest.get('path_clear')}"
    )


def _build_prompt(message: str, context: dict[str, Any], semantic: str) -> str:
    """Build a small user prompt paired with NINE_BALL_COACH_SYSTEM_PROMPT."""
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    prompt = (
        f"問題：{message}\n"
        f"摘要：{semantic}\n"
        f"規則：{_compact_rules_summary(semantic_context)}\n"
        f"合法目標：{_compact_legal_target_summary(semantic_context)}\n"
        f"路徑規劃：{_summarize_multi_plan(context.get('multi_plan'))}\n"
    )
    return prompt[:AI_COACH_MAX_PROMPT_CHARS]


def _call_vllm(message: str, context: dict[str, Any], semantic: str) -> str:
    """Call the OpenAI-compatible vLLM chat completion endpoint."""
    payload = {
        "model": AI_COACH_MODEL,
        "messages": [
            {"role": "system", "content": NINE_BALL_COACH_SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(message, context, semantic)},
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": AI_COACH_MAX_TOKENS,
    }

    response = requests.post(AI_COACH_API_URL, json=payload, timeout=AI_COACH_VLLM_TIMEOUT_SECONDS)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:700] if response is not None else ""
        raise RuntimeError(f"vLLM HTTP {response.status_code}: {body}") from exc
    data = response.json()
    return _clean_recommendation(str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip())


def _clean_recommendation(text: str) -> str:
    """Convert model markdown/JSON wrappers into plain coach text."""
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    if cleaned.startswith("{"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                for key in ("建議", "suggestion", "recommendation", "reply", "answer"):
                    value = parsed.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        except json.JSONDecodeError:
            pass

    for prefix in ("建議：", "建議:", "recommendation:", "Recommendation:"):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix):].strip()
    return cleaned


async def _coach_result(message: str, context: dict[str, Any]) -> dict[str, Any]:
    """Generate one coach result for chat or explicit suggestion requests."""
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    if not semantic_context and isinstance(context.get("context"), dict):
        nested = context["context"].get("semantic_context")
        semantic_context = nested if isinstance(nested, dict) else {}

    if not semantic_context:
        semantic_context = {
            "valid": False,
            "reason": "NO_SEMANTIC_CONTEXT",
            "summary": "主後端沒有提供檯面語意資料。",
        }
    context = {**context, "semantic_context": semantic_context}

    semantic = _semantic_description(semantic_context)
    start = time.time()
    try:
        recommendation = await asyncio.to_thread(_call_vllm, message, context, semantic)
        error = None
    except Exception as exc:
        recommendation = ""
        error = str(exc)

    return {
        "timestamp": datetime.now().isoformat(),
        "semantic_description": semantic,
        "recommendation": recommendation,
        "confidence": 0.8 if recommendation else 0.0,
        "processing_time": round(time.time() - start, 3),
        "error": error,
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """Return service health and model routing information."""
    return {
        "status": "ok",
        "service": "ai_coach",
        "model": AI_COACH_MODEL,
        "vllm_url": AI_COACH_API_URL,
    }


@app.websocket("/ws/coach")
async def coach_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint used by the main backend CoachBridge."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")
            request_id = message.get("request_id") or str(uuid.uuid4())
            payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}

            if msg_type == "analysis.request":
                semantic_context = payload.get("semantic_context") if isinstance(payload.get("semantic_context"), dict) else {}
                if not semantic_context.get("stable"):
                    continue
                result = await _coach_result("請根據目前檯面產生一則九號球建議。", payload)
            elif msg_type == "chat.request":
                chat_message = str(payload.get("message", "")).strip()
                context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
                if isinstance(payload.get("semantic_context"), dict):
                    context["semantic_context"] = payload["semantic_context"]
                if not chat_message:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "coach.error",
                                "request_id": request_id,
                                "status": "error",
                                "payload": {"error": "Missing message"},
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue
                result = await _coach_result(chat_message, context)
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "coach.error",
                            "request_id": request_id,
                            "status": "error",
                            "payload": {"error": f"Unsupported message type: {msg_type}"},
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            response_type = "coach.error" if result.get("error") else "coach.result"
            await websocket.send_text(
                json.dumps(
                    {
                        "type": response_type,
                        "request_id": request_id,
                        "status": "error" if result.get("error") else "success",
                        "payload": result,
                    },
                    ensure_ascii=False,
                )
            )
    except WebSocketDisconnect:
        return


def main() -> None:
    """Run the standalone AI Coach service."""
    uvicorn.run(
        app,
        host=AI_COACH_HOST,
        port=AI_COACH_PORT,
        use_colors=False,
        ws_ping_interval=AI_COACH_SERVER_WS_PING_INTERVAL,
        ws_ping_timeout=AI_COACH_SERVER_WS_PING_TIMEOUT,
    )


if __name__ == "__main__":
    main()
