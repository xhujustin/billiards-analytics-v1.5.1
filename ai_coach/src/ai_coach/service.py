from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

import requests
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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
AI_COACH_MODEL = os.getenv("AI_COACH_MODEL", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
if AI_COACH_MODEL == "/home/lucian039/gemma-4-awq":
    AI_COACH_MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
AI_COACH_VLLM_TIMEOUT_SECONDS = float(os.getenv("AI_COACH_VLLM_TIMEOUT_SECONDS", "90"))
AI_COACH_MAX_TOKENS = int(os.getenv("AI_COACH_MAX_TOKENS", "80"))
AI_COACH_MAX_PROMPT_CHARS = int(os.getenv("AI_COACH_MAX_PROMPT_CHARS", "900"))
AI_COACH_STREAMING_ENABLED = os.getenv("AI_COACH_STREAMING_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
AI_COACH_SERVER_WS_PING_INTERVAL = _optional_float_env("AI_COACH_SERVER_WS_PING_INTERVAL", "0")
AI_COACH_SERVER_WS_PING_TIMEOUT = _optional_float_env("AI_COACH_SERVER_WS_PING_TIMEOUT", "0")


NINE_BALL_COACH_SYSTEM_PROMPT = (
    "你是九號球 AI Coach，只能根據後端提供的 JSON 與規則回答。"
    "若 context.schema_version 是 coach.context.v1，必須優先使用 planner.best_route "
    "與 planner.position_play；不得自行發明球路、袋口、母球走位或下一球目的。"
    "若 planner 欄位不足，但 semantic_context 有合法目標、袋口、清線與阻擋資訊，"
    "請依這些畫面語意做保守判斷，不要說資料不足。"
    "回答必須使用繁體中文，語氣像 CueVex 專業教練，直接回答玩家問題。"
    "不要使用固定欄位格式、Markdown、系統狀態、planner、YOLO、座標或原始數據字眼。"
    "舊版 context.multi_plan 仍可作為補充，但不得覆蓋 planner/position_play。"
)

SUPPORTED_LOCALES = {"zh-TW", "zh-CN", "en-US"}


SYSTEM_OPERATION_MANUAL = """
CueVex 系統操作手冊：
- 主選單：即時影像=即時畫面/直播/鏡頭畫面/辨識畫面/現在畫面/球桌畫面；回放記錄=回放/錄影/影片/重播/歷史紀錄/打過的局/練習紀錄；練習模式=練球/訓練/單球練習/球型練習/straight/cut/bank/combo；遊戲模式=比賽/對戰/九號球/正式局；AI Coach=教練/聊天/產生建議/問下一桿/對話紀錄。
- 設定 > 一般：後端 API URL、WebSocket URL、AI Coach 連線、串流品質/畫質、語言、開發模式、本機設定保存。
- 設定 > 外觀：深色/淺色/跟隨系統、字體大小、強調色；強調色包含預設、翡翠綠、靛藍、琥珀、青色。
- 設定 > 相機：相機裝置、暖光/白光燈光 profile、曝光、ISO、亮度、對比度、飽和度、銳利度、白平衡、色溫。
- 設定 > 球桌校正：球桌布色、自訂 HSV、ROI 微調、四點 ROI、顏色校正、投影機校正；桌面框歪、邊框不準、球跑出桌外、綠框、偵測框都通常到這裡處理。
- 設定 > 球桌校正 > 顏色校正：球色錯、辨識成錯的球、顏色不準、HSV、色票、掃描球色、套用顏色、儲存顏色設定檔。
- 設定 > 追蹤：球桿線、追蹤線、軌跡、疊圖、辨識顯示、提示線、YOLO 繪製模式；練習模式內也可切換 none/tactical/full。
- 帳號管理：登入/註冊/忘記密碼在登入畫面；登入後可改名稱、密碼、安全問題、看登入紀錄、刪除帳號。訪客模式不保存個人設定與對話紀錄到帳號資料庫。
- 回放記錄：可看遊戲模式或練習模式錄影列表、播放、刪除、事件回放與統計。
- 練習模式：可選一般練習或球型練習；球型包含 straight、cut、bank、combo。
- 遊戲模式：開始九號球對戰流程，後續可進回放記錄查看。
- AI Coach：左側可開啟對話、產生建議、新增對話、切換、重新命名、釘選或刪除。產生建議需要當前畫面穩定。
回答系統問題時，要先猜玩家的非正式說法最接近哪個功能，再給最短路徑。格式偏向：「你說的 X 比較像是 Y，請到 Z。」若有兩個可能，補一句「如果你指的是 A，則到 B。」不要第一句就說不知道。
"""


class ConversationRouter:
    """Route user messages before deciding whether technical context is allowed."""

    GREETING_RE = re.compile(r"(嗨|你好|哈囉|哈啰|在嗎|在吗|早安|早上好|早啊|午安|晚安|hi|hello|good\s*morning)", re.IGNORECASE)
    IDENTITY_RE = re.compile(r"(我是\s*(gay|同志|同性戀|同性恋|雙性戀|双性恋|跨性別|跨性别)|我喜歡男生|我喜欢男生|我喜歡女生|我喜欢女生)", re.IGNORECASE)
    PRIVATE_RE = re.compile(r"(女朋友|男朋友|幾歲|几岁|年齡|年龄|生日|單身|单身|你媽媽|你妈|你爸|我當你媽|我当你妈|我當你媽媽|我当你妈妈|我帥|我帅|我漂亮|我好看|我醜|我丑|你覺得我|你觉得我|長得帥|长得帅|長得好看|长得好看)", re.IGNORECASE)
    ROMANCE_RE = re.compile(r"(戀愛|恋爱|激情|曖昧|暧昧|約會|约会|親親|亲亲|抱抱|愛你|爱你|跟你交往|跟你談|跟你谈)", re.IGNORECASE)
    MOOD_RE = re.compile(r"(很爛|打得爛|打得烂|好爛|好烂|很糟|心情不好|沮喪|沮丧|挫折|沒手感|没手感|雞掰|機掰|靠北|靠夭|幹|干|煩死|烦死)", re.IGNORECASE)
    GOODBYE_RE = re.compile(r"(先這樣|先这样|掰掰|拜拜|再見|再见|下次聊|結束)", re.IGNORECASE)
    STATUS_RE = re.compile(r"(辨識|识别|畫面|画面|正常嗎|正常吗|fps|yolo|偵測|侦测|系統|系统|roi|光線|光线|太亮|太暗|校正)", re.IGNORECASE)
    SHOT_RE = re.compile(r"(這一桿|这一杆|這桿|这杆|剛剛那桿|刚刚那杆|打得好|力道|擊球|击球|球打得)", re.IGNORECASE)
    TACTIC_RE = re.compile(r"(下一顆|下一颗|打哪|怎麼打|怎么打|戰術|战术|路線|路线|袋口|建議|建议)", re.IGNORECASE)
    ACCOUNT_RE = re.compile(r"(登入|登錄|登录|訪客|访客|帳號|账号|存不了|保存|儲存|储存|sqlite|設定|设置)", re.IGNORECASE)
    UI_RE = re.compile(r"(顏色|颜色|好看|翡翠綠|翡翠绿|美感|配色|ui|介面|界面|語言|语言|換語言|换语言|切換語言|切换语言|球桌邊框|球桌边框|桌面邊框|桌面边框|球桌邊界|球桌边界|桌面邊界|桌面边界|球桌範圍|球桌范围|桌面範圍|桌面范围|邊框|边框|roi|ROI|四點|四点|校正|調整球桌|调整球桌|調整桌面|调整桌面|去哪裡調整|去哪里调整)", re.IGNORECASE)

    RULE_RE = re.compile(r"(合法碰球|合法撞球|合法擊球|犯規|九號球規則|9\s*號球規則|nine\s*ball.*rule|rule)", re.IGNORECASE)
    KNOWLEDGE_RE = re.compile(r"(?=.*(撞球|台球|pool|billiard|snooker|斯諾克|斯诺克))(?=.*(選手|选手|球員|球员|名將|名将|有名|著名|知名|世界上|世界級|世界级|冠軍|冠军|高手|有哪些|誰|谁|介紹|介绍))", re.IGNORECASE)

    @classmethod
    def route(cls, message: str) -> str:
        text = str(message or "").strip()
        if cls.GOODBYE_RE.search(text):
            return "social_goodbye"
        if cls.IDENTITY_RE.search(text):
            return "social_identity"
        if cls.ROMANCE_RE.search(text):
            return "social_romance"
        if cls.PRIVATE_RE.search(text):
            return "social_private"
        if cls.MOOD_RE.search(text):
            return "social_mood"
        if cls.GREETING_RE.search(text):
            return "social_greeting"
        if cls.RULE_RE.search(text):
            return "rule_support"
        if cls.KNOWLEDGE_RE.search(text):
            return "knowledge_support"
        if cls.ACCOUNT_RE.search(text) or cls.UI_RE.search(text):
            return "ui_support"
        if cls.STATUS_RE.search(text):
            return "system_status"
        if cls.SHOT_RE.search(text):
            return "shot_analysis"
        if cls.TACTIC_RE.search(text):
            return "tactic"
        return "technical"

    @staticmethod
    def is_social(route: str) -> bool:
        return route.startswith("social_")


def _normalize_locale(value: Any) -> str:
    locale = str(value or "zh-TW").replace("_", "-")
    aliases = {
        "zh": "zh-TW",
        "zh-tw": "zh-TW",
        "zh-hant": "zh-TW",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "en": "en-US",
        "en-us": "en-US",
    }
    normalized = aliases.get(locale.lower(), locale)
    return normalized if normalized in SUPPORTED_LOCALES else "zh-TW"


def _locale_instruction(locale: str) -> str:
    instructions = {
        "zh-TW": "回答必須使用繁體中文。",
        "zh-CN": "回答必须使用简体中文。",
        "en-US": "Reply in concise American English.",
    }
    return instructions.get(locale, instructions["zh-TW"])


def _system_prompt(locale: str) -> str:
    return (
        NINE_BALL_COACH_SYSTEM_PROMPT.replace("回答必須使用繁體中文，", "")
        + _locale_instruction(locale)
        + " 只回答玩家問到的內容，避免固定欄位格式與完整分析段落。"
    )


PLANNER_FIELDS = (
    "target_ball",
    "target_ball_number",
    "ball_number",
    "target_pocket",
    "pocket",
    "route_type",
    "success_prob",
    "stroke_advice",
    "next_ball",
    "expected_point",
    "target_zone",
    "risk_flags",
)

POCKET_LABELS_ZH_TW = {
    "top_left": "左上袋",
    "top_middle": "上中袋",
    "top_center": "上中袋",
    "top_right": "右上袋",
    "bottom_left": "左下袋",
    "bottom_middle": "下中袋",
    "bottom_center": "下中袋",
    "bottom_right": "右下袋",
}

ROUTE_LABELS_ZH_TW = {
    "straight": "直球",
    "direct": "直球",
    "cut": "切球",
    "bank": "翻袋",
    "combo": "組合球",
    "kick": "解球",
    "kick_escape": "解球",
    "safe_escape": "安全球",
    "contact_only": "先求合法碰球",
}

POWER_LABELS_ZH_TW = {
    "low": "小力",
    "medium": "中等力道",
    "medium_high": "中高力道",
    "high": "大力",
}

SPIN_LABELS_ZH_TW = {
    "none": "中桿",
    "center": "中桿",
    "top_spin": "高桿",
    "draw": "低桿",
    "left_english": "左塞",
    "right_english": "右塞",
    "outside_english": "外塞",
    "running_english": "順塞",
    "continuous_tip": "依手動桿點",
}


def _short_json(value: Any, limit: int = 240) -> str:
    """Serialize compact JSON for prompts with a hard character limit."""
    if value in (None, "", [], {}):
        return "無"
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else f"{text[:limit]}..."


def _request_type(context: dict[str, Any]) -> str:
    request = context.get("request") if isinstance(context.get("request"), dict) else {}
    return str(request.get("type") or "").strip().lower()


def _response_mode(context: dict[str, Any]) -> str:
    request = context.get("request") if isinstance(context.get("request"), dict) else {}
    mode = request.get("response_mode")
    if not mode and isinstance(context.get("context"), dict):
        nested_request = context["context"].get("request")
        if isinstance(nested_request, dict):
            mode = nested_request.get("response_mode")
    if not mode:
        mode = context.get("active_response_mode")
    return str(mode or "").strip().lower()


def _is_action_suggestion_request(context: dict[str, Any]) -> bool:
    return _request_type(context) == "action_suggestion" or _response_mode(context) == "action_suggestion"


def _is_suggestion_request(message: str, context: dict[str, Any]) -> bool:
    if _request_type(context) in {"suggest", "analysis"}:
        return True
    text = str(message or "")
    return any(keyword in text for keyword in ("建議", "下一桿", "怎麼打", "怎麼走"))


def _planner_best_route(context: dict[str, Any]) -> dict[str, Any]:
    planner = _planner_source(context)
    best_route = planner.get("best_route") if isinstance(planner.get("best_route"), dict) else {}
    return best_route if isinstance(best_route, dict) else {}


def _planner_result(context: dict[str, Any]) -> dict[str, Any]:
    planner = _planner_source(context)
    result = planner.get("result") if isinstance(planner.get("result"), dict) else {}
    return result if isinstance(result, dict) else {}


def _planner_position_play(context: dict[str, Any], best_route: dict[str, Any]) -> dict[str, Any]:
    planner = _planner_source(context)
    position_play = planner.get("position_play") if isinstance(planner.get("position_play"), dict) else {}
    if position_play:
        return position_play
    route_position = best_route.get("position_play") if isinstance(best_route.get("position_play"), dict) else {}
    return route_position if isinstance(route_position, dict) else {}


def _normalize_pocket_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    return POCKET_LABELS_ZH_TW.get(lowered, text)


def _pocket_name_from_point(point: Any, context: dict[str, Any], max_distance: float = 45.0) -> str:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return ""
    try:
        px = float(point[0])
        py = float(point[1])
    except (TypeError, ValueError):
        return ""

    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    table = semantic_context.get("table") if isinstance(semantic_context.get("table"), dict) else {}
    pockets = table.get("pockets") if isinstance(table.get("pockets"), list) else []
    best_name = ""
    best_distance = max_distance
    for pocket in pockets:
        if not isinstance(pocket, dict):
            continue
        center = pocket.get("center")
        if not isinstance(center, (list, tuple)) or len(center) < 2:
            continue
        try:
            distance = ((px - float(center[0])) ** 2 + (py - float(center[1])) ** 2) ** 0.5
        except (TypeError, ValueError):
            continue
        if distance <= best_distance:
            best_distance = distance
            best_name = _normalize_pocket_name(pocket.get("name"))
    return best_name


def _target_pocket_label(best_route: dict[str, Any], context: dict[str, Any]) -> str:
    explicit = (
        best_route.get("target_pocket")
        or best_route.get("pocket")
        or best_route.get("target_pocket_name")
    )
    explicit_label = _normalize_pocket_name(explicit)
    if explicit_label:
        return explicit_label

    for segment in best_route.get("route_segments") or []:
        if not isinstance(segment, dict):
            continue
        points = segment.get("points")
        if segment.get("type") == "object_to_pocket" and isinstance(points, list) and points:
            label = _pocket_name_from_point(points[-1], context)
            if label:
                return label

    path_points = best_route.get("path_points")
    if isinstance(path_points, list) and path_points:
        return _pocket_name_from_point(path_points[-1], context)
    return ""


def _format_percent(value: Any) -> str:
    try:
        pct = round(float(value) * 100)
    except (TypeError, ValueError):
        return "未評估"
    return f"{pct}%"


def _stroke_labels(best_route: dict[str, Any], position_play: dict[str, Any]) -> tuple[str, str]:
    stroke_hint = best_route.get("stroke_hint") if isinstance(best_route.get("stroke_hint"), dict) else {}
    stroke_advice = (
        position_play.get("stroke_advice")
        if isinstance(position_play.get("stroke_advice"), dict)
        else {}
    )
    power = stroke_advice.get("speed") or stroke_hint.get("power")
    spin = stroke_advice.get("english") or stroke_hint.get("spin")
    return (
        POWER_LABELS_ZH_TW.get(str(power or "").strip().lower(), str(power or "中等力道")),
        SPIN_LABELS_ZH_TW.get(str(spin or "").strip().lower(), str(spin or "中桿")),
    )


def _deterministic_no_route_reply(context: dict[str, Any]) -> str:
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    legal = _legal_target(semantic_context.get("balls"))
    target = legal.get("number") if isinstance(legal, dict) else None
    nearest = legal.get("nearest_pocket") if isinstance(legal, dict) and isinstance(legal.get("nearest_pocket"), dict) else {}
    blocked_by = nearest.get("blocked_by") or (legal.get("cue_blocked_by") if isinstance(legal, dict) else []) or []
    blocked_text = "，路線可能被其他球阻擋" if blocked_by else ""
    target_text = f"#{target}" if target is not None else "合法目標球"
    return (
        f"目標球/袋：先以 {target_text} 為合法首碰，但目前 planner 沒有可採信的進袋路線{blocked_text}。\n"
        "力道：小力到中等力道。\n"
        "桿法：中桿，先確保合法碰球。\n"
        "母球走位：不要強行指定走位，優先停在檯面中區或避開袋口。\n"
        "下一球目的：等路線規劃穩定後再選擇進攻袋口。\n"
        "風險：若直接指定袋口，可能與實際球路不符。"
    )


def _deterministic_route_reply(context: dict[str, Any]) -> str:
    """Build a grounded suggestion from planner data without letting the LLM invent a pocket."""
    if _context_schema_version(context) != "coach.context.v1":
        return ""

    best_route = _planner_best_route(context)
    result = _planner_result(context)
    if not best_route:
        return _deterministic_no_route_reply(context)

    target = best_route.get("target_ball_number") or best_route.get("target_ball") or best_route.get("ball_number")
    pocket = _target_pocket_label(best_route, context)
    route_type = ROUTE_LABELS_ZH_TW.get(str(best_route.get("route_type") or "").strip().lower(), str(best_route.get("route_type") or "規劃路線"))
    position_play = _planner_position_play(context, best_route)
    power, spin = _stroke_labels(best_route, position_play)
    success = _format_percent(best_route.get("success_prob"))
    risk_flags = best_route.get("risk_flags") if isinstance(best_route.get("risk_flags"), list) else []
    route_error = result.get("error") or best_route.get("error")

    if not pocket:
        return _deterministic_no_route_reply(context)

    next_ball = position_play.get("next_ball") if isinstance(position_play.get("next_ball"), dict) else position_play.get("next_ball")
    if isinstance(next_ball, dict):
        next_ball_text = f"#{next_ball.get('number')}" if next_ball.get("number") is not None else "下一顆球"
    elif next_ball not in (None, "", [], {}):
        next_ball_text = f"#{next_ball}"
    else:
        next_ball_text = "下一顆球"

    landing = best_route.get("cue_landing_zone") if isinstance(best_route.get("cue_landing_zone"), dict) else {}
    landing_label = landing.get("label") or "planner 標示的母球落點區"
    risk_text = "、".join(str(flag) for flag in risk_flags[:3]) if risk_flags else f"成功率約 {success}"
    if route_error:
        risk_text = f"{route_error}；{risk_text}"

    return (
        f"目標球/袋：打 #{target}，走 {route_type} 到 {pocket}。\n"
        f"力道：{power}。\n"
        f"桿法：{spin}。\n"
        f"母球走位：讓母球留在 {landing_label}，不要過度發力。\n"
        f"下一球目的：保留對 {next_ball_text} 的角度。\n"
        f"風險：{risk_text}。"
    )


def _risk_tokens(context: dict[str, Any], best_route: dict[str, Any], result: dict[str, Any]) -> str:
    tokens: list[str] = []
    for source in (best_route, result, _planner_position_play(context, best_route)):
        if not isinstance(source, dict):
            continue
        flags = source.get("risk_flags")
        if isinstance(flags, list):
            tokens.extend(str(flag) for flag in flags)
        for key in ("risk", "risk_level", "warning", "error"):
            value = source.get(key)
            if value not in (None, "", [], {}):
                tokens.append(str(value))
    shot_event = _context_dict(context, "shot_event")
    if shot_event.get("cue_ball_potted") is True:
        tokens.append("cue_ball_potted")
    return " ".join(tokens).lower()


def _has_scratch_risk(context: dict[str, Any], best_route: dict[str, Any], result: dict[str, Any]) -> bool:
    tokens = _risk_tokens(context, best_route, result)
    return any(
        marker in tokens
        for marker in (
            "scratch",
            "cue_ball_potted",
            "cue pocket",
            "cue_pocket",
            "洗袋",
            "母球落袋",
            "母球進袋",
        )
    )


def _action_power_phrase(best_route: dict[str, Any], position_play: dict[str, Any]) -> str:
    stroke_hint = best_route.get("stroke_hint") if isinstance(best_route.get("stroke_hint"), dict) else {}
    stroke_advice = position_play.get("stroke_advice") if isinstance(position_play.get("stroke_advice"), dict) else {}
    power = str(stroke_advice.get("speed") or stroke_hint.get("power") or "").strip().lower()
    if power in {"low", "soft", "slow"}:
        return "小力出桿"
    if power in {"high", "hard", "fast"}:
        return "避免重擊，改用中等力道"
    if power in {"medium_high"}:
        return "中等偏穩的力道"
    return "中等力道"


def _action_spin_phrase(best_route: dict[str, Any], position_play: dict[str, Any]) -> str:
    stroke_hint = best_route.get("stroke_hint") if isinstance(best_route.get("stroke_hint"), dict) else {}
    stroke_advice = position_play.get("stroke_advice") if isinstance(position_play.get("stroke_advice"), dict) else {}
    spin = str(stroke_advice.get("english") or stroke_hint.get("spin") or "").strip().lower()
    if spin in {"draw", "low", "low_cue"}:
        return "低桿"
    if spin in {"top", "top_spin", "follow"}:
        return "高桿"
    if "left" in spin:
        return "左塞"
    if "right" in spin:
        return "右塞"
    return "中桿"


def _action_suggestion_reply(context: dict[str, Any]) -> str:
    best_route = _planner_best_route(context)
    result = _planner_result(context)
    if not best_route:
        return _clean_action_suggestion(
            "目前進袋路線不穩，強攻容易讓母球失位或留下空檔。請用中桿小力完成合法碰球，讓母球停在檯面中區。這樣能降低失誤成本，保留下一桿選擇。"
        )

    position_play = _planner_position_play(context, best_route)
    if _has_scratch_risk(context, best_route, result):
        return _clean_action_suggestion(
            "這條線容易把母球帶向袋口，直接推進有洗袋風險。建議改用低桿擊打母球中心偏下方位，並降低出桿力道。這樣能抵消向前動能，保留母球控制。"
        )

    route_type = str(best_route.get("route_type") or "").strip().lower()
    risk_tokens = _risk_tokens(context, best_route, result)
    power = _action_power_phrase(best_route, position_play)
    spin = _action_spin_phrase(best_route, position_play)

    if "thin" in risk_tokens:
        text = f"目前切球點偏薄，目標球容易少吃角度而偏出袋線。請將瞄準點向厚邊修正約 5mm，使用{spin}與{power}。這樣能補足撞擊厚度，讓母球停在可控區域。"
    elif "thick" in risk_tokens:
        text = f"目前切球點過厚，母球容易吃太多角度而偏離預期路線。請將瞄準點向薄邊修正約 5mm，使用{spin}與{power}。這樣能讓目標球路更乾淨，降低母球失控風險。"
    elif route_type in {"cut", "thin_cut"}:
        text = f"這顆球需要乾淨切入，瞄準誤差會直接放大成路線偏差。請把瞄準點微調約 5mm，使用{spin}與{power}。這樣能提高進球線穩定度，優先保留母球走位。"
    elif route_type in {"bank", "kick", "kick_escape"}:
        text = f"這條路線需要先碰對第一接觸點，力道過大會放大反彈誤差。請用{spin}小力處理第一碰撞點，讓母球留在檯面中區。這樣能降低送分風險。"
    else:
        text = f"目前路線以穩定送球為主，過度加塞會讓母球路徑變難控。請保持中線瞄準，使用{spin}與{power}穩定送桿。這樣能讓母球停在下一桿容易銜接的位置。"
    return _clean_action_suggestion(text)


def _clean_action_suggestion(text: str) -> str:
    cleaned = _clean_recommendation(text)
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)
    cleaned = re.sub(r"</?[^>]+>", "", cleaned)
    cleaned = re.sub(r"[*_`#>|-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned.replace("\r", " ").replace("\n", " ")).strip()

    banned = re.compile(
        r"(FPS|VRAM|Coordinates|Deviation|座標|坐標|debug|JSON|planner|YOLO|系統|硬體|原始|"
        r"目標球/袋|風險：|力道：|桿法：|Deviation\s*%)",
        re.IGNORECASE,
    )
    if banned.search(cleaned):
        parts = re.split(r"[。！？!?]", cleaned)
        safe_parts = [part.strip() for part in parts if part.strip() and not banned.search(part)]
        cleaned = "。".join(safe_parts[:2]).strip()
        if cleaned:
            cleaned += "。"

    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", cleaned)
    if sentences:
        cleaned = "".join(sentences[:3]).strip()
    cleaned = cleaned[:260].strip()
    if not cleaned:
        cleaned = "目前進袋路線不穩，強攻容易留下空檔。請用中桿小力穩定完成合法碰球，讓母球停在檯面中區。這樣能保留下一桿選擇。"
    if not re.search(r"[。！？!?]$", cleaned):
        cleaned += "。"
    return cleaned


def _compact_dict(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Return selected non-empty fields from a dict without mutating source."""
    if not isinstance(source, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in fields:
        value = source.get(field)
        if value not in (None, "", [], {}):
            compact[field] = value
    return compact


def _legal_target(balls: Any) -> Optional[dict[str, Any]]:
    """Return the single legal target marked by CoachSemanticAdapter."""
    if not isinstance(balls, list):
        return None
    for ball in balls:
        if isinstance(ball, dict) and ball.get("is_legal_target") is True:
            return ball
    return None


def _compact_legal_target_summary(semantic_context: dict[str, Any]) -> str:
    """Summarize only the legal target to stay under Gemma's token limit."""
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


def _compact_remaining_balls_summary(semantic_context: dict[str, Any]) -> str:
    """Summarize visible object ball numbers so Gemma can answer next-ball follow-ups."""
    balls = semantic_context.get("balls") if isinstance(semantic_context.get("balls"), list) else []
    seen: set[int] = set()
    numbers: list[int] = []
    for ball in balls:
        if not isinstance(ball, dict):
            continue
        try:
            number = int(ball.get("number"))
        except (TypeError, ValueError):
            continue
        if number <= 0 or number in seen:
            continue
        seen.add(number)
        numbers.append(number)
    numbers.sort()
    legal = _legal_target(balls)
    legal_number = None
    if isinstance(legal, dict):
        try:
            legal_number = int(legal.get("number"))
        except (TypeError, ValueError):
            legal_number = None
    after_legal = next((number for number in numbers if legal_number is not None and number > legal_number), None)
    return _short_json(
        {
            "visible_object_numbers": numbers,
            "current_legal_target": legal_number,
            "next_lowest_after_current_if_potted": after_legal,
        },
        limit=180,
    )


def _summarize_multi_plan(raw_multi_plan: Any) -> str:
    """Keep only the legacy route-planner target fields useful to the LLM."""
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


def _context_schema_version(context: dict[str, Any]) -> Optional[str]:
    """Return the schema version from root or nested coach context."""
    version = context.get("schema_version")
    if isinstance(version, str):
        return version
    nested = context.get("context")
    if isinstance(nested, dict) and isinstance(nested.get("schema_version"), str):
        return nested["schema_version"]
    return None


def _planner_source(context: dict[str, Any]) -> dict[str, Any]:
    """Return planner payload from root or nested coach context."""
    planner = context.get("planner")
    if isinstance(planner, dict):
        return planner
    nested = context.get("context")
    if isinstance(nested, dict) and isinstance(nested.get("planner"), dict):
        return nested["planner"]
    return {}


def _summarize_coach_context_v1(context: dict[str, Any]) -> str:
    """Summarize coach.context.v1 planner route and position play guidance."""
    if _context_schema_version(context) != "coach.context.v1":
        return "無"

    planner = _planner_source(context)
    best_route = planner.get("best_route") if isinstance(planner.get("best_route"), dict) else {}
    position_play = (
        planner.get("position_play") if isinstance(planner.get("position_play"), dict) else {}
    )
    compact_best_route = _compact_dict(best_route, PLANNER_FIELDS)
    target_ball = (
        compact_best_route.get("target_ball_number")
        or compact_best_route.get("target_ball")
        or compact_best_route.get("ball_number")
    )
    if target_ball not in (None, "", [], {}):
        compact_best_route["打哪顆"] = target_ball
    summary = {
        "schema_version": "coach.context.v1",
        "best_route": compact_best_route,
        "position_play": _compact_dict(position_play, PLANNER_FIELDS),
    }
    return _short_json(summary, limit=520)


def _semantic_description(semantic_context: dict[str, Any]) -> str:
    """Create a concise semantic summary from backend geometry results."""
    if not semantic_context.get("valid"):
        reason = semantic_context.get("reason") or semantic_context.get("unstable_reason") or "UNKNOWN"
        return f"目前語意資料無效，reason={reason}"

    legal = _legal_target(semantic_context.get("balls"))
    if not legal:
        return "找不到合法目標球"

    nearest = legal.get("nearest_pocket") if isinstance(legal.get("nearest_pocket"), dict) else {}
    return (
        f"合法目標球={legal.get('number')}; "
        f"cue_path={legal.get('cue_path_clear')}; "
        f"pocket={nearest.get('name')}; "
        f"pocket_path={nearest.get('path_clear')}"
    )


def _build_prompt(message: str, context: dict[str, Any], semantic: str) -> str:
    """Build a small user prompt paired with NINE_BALL_COACH_SYSTEM_PROMPT."""
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    prompt = (
        "任務：根據目前畫面回答玩家問題。"
        "若路線規劃有明確 best_route/position_play，優先照它回答；"
        "若路線規劃為空，但語意資料有效，請用合法目標、最近袋口、清線狀態與阻擋資訊判斷打法。"
        "不要因為路線規劃為空就回覆資料不足，也不要要求玩家指定更多情境作為第一反應。"
        "只回答玩家問到的事項，不要主動延伸成完整戰術報告。"
        "如果玩家問的是可不可行，先直接說可或不建議，再給一個原因；"
        "如果玩家同時問下一顆，才補下一顆或下一步。"
        "輸出要求：自然繁體中文 1 到 2 句；不要固定列出欄位；不要 Markdown；"
        "不要出現 planner、YOLO、資料不足、座標、FPS、Deviation 或原始 JSON。"
        "不要同時輸出目標球、替代打法、走位、風險等多個面向，除非玩家明確逐項詢問。\n"
        f"玩家問題：{message}\n"
        f"目前畫面摘要：{semantic}\n"
        f"九號球規則摘要：{_compact_rules_summary(semantic_context)}\n"
        f"合法目標與袋口線索：{_compact_legal_target_summary(semantic_context)}\n"
        f"剩餘球號摘要：{_compact_remaining_balls_summary(semantic_context)}\n"
        f"coach.context.v1 路線規劃摘要：{_summarize_coach_context_v1(context)}\n"
        f"舊版 multi_plan：{_summarize_multi_plan(context.get('multi_plan'))}\n"
    )
    return prompt[:AI_COACH_MAX_PROMPT_CHARS]


def _call_vllm(message: str, context: dict[str, Any], semantic: str, locale: str = "zh-TW") -> str:
    """Call the OpenAI-compatible vLLM chat completion endpoint."""
    payload = {
        "model": AI_COACH_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt(locale)},
            {"role": "user", "content": _build_prompt(message, context, semantic)},
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": AI_COACH_MAX_TOKENS,
    }
    return _clean_recommendation(_complete_vllm_payload(payload))


def _extract_chat_completion_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
    if isinstance(delta.get("content"), str):
        return delta["content"]
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    if isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(choice.get("text"), str):
        return choice["text"]
    return ""


def _iter_vllm_payload_chunks(payload: dict[str, Any]):
    stream_payload = dict(payload)
    stream_payload["stream"] = True
    response = requests.post(
        AI_COACH_API_URL,
        json=stream_payload,
        timeout=AI_COACH_VLLM_TIMEOUT_SECONDS,
        stream=True,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:700] if response is not None else ""
        raise RuntimeError(f"vLLM HTTP {response.status_code}: {body}") from exc

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        chunk = _extract_chat_completion_text(data)
        if chunk:
            yield chunk


def _complete_vllm_payload(payload: dict[str, Any]) -> str:
    if AI_COACH_STREAMING_ENABLED:
        return "".join(_iter_vllm_payload_chunks(payload)).strip()

    response = requests.post(AI_COACH_API_URL, json=payload, timeout=AI_COACH_VLLM_TIMEOUT_SECONDS)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:700] if response is not None else ""
        raise RuntimeError(f"vLLM HTTP {response.status_code}: {body}") from exc
    data = response.json()
    return _extract_chat_completion_text(data).strip()


def _build_action_suggestion_prompt(context: dict[str, Any]) -> str:
    planner = _planner_source(context)
    best_route = planner.get("best_route") if isinstance(planner, dict) and isinstance(planner.get("best_route"), dict) else {}
    position_play = planner.get("position_play") if isinstance(planner, dict) and isinstance(planner.get("position_play"), dict) else {}
    stroke_hint = best_route.get("stroke_hint") if isinstance(best_route.get("stroke_hint"), dict) else {}
    stroke_advice = position_play.get("stroke_advice") if isinstance(position_play.get("stroke_advice"), dict) else {}
    shot_event = _context_dict(context, "shot_event")
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    risk_flags = best_route.get("risk_flags") if isinstance(best_route.get("risk_flags"), list) else []
    route_state = "已有可參考路線" if best_route else "沒有可靠進攻路線"
    stable_state = "球已接近靜止" if semantic_context.get("stable") else "畫面或球位仍可能變動"
    semantic_summary = _semantic_description(semantic_context)
    legal_target_summary = _compact_legal_target_summary(semantic_context)
    rules_summary = _compact_rules_summary(semantic_context)
    remaining_balls_summary = _compact_remaining_balls_summary(semantic_context)
    route_summary = _summarize_coach_context_v1(context)
    lines = [
        f"YOLO 辨識後的球局摘要：{semantic_summary}。",
        f"九號球規則摘要：{rules_summary}。",
        f"合法目標與袋口清線：{legal_target_summary}。",
        f"剩餘球號摘要：{remaining_balls_summary}。",
        f"路線規劃摘要：{route_summary}。",
        f"目前盤面狀態：{stable_state}；{route_state}。",
    ]
    if best_route:
        lines.extend(
            [
                f"路線型態：{best_route.get('route_type') or '未明確'}。",
                f"風險線索：{', '.join(str(flag) for flag in risk_flags[:4]) if risk_flags else '未標示特殊風險'}。",
                f"建議力道線索：{stroke_advice.get('speed') or stroke_hint.get('power') or '未標示'}。",
                f"建議桿法線索：{stroke_advice.get('english') or stroke_hint.get('spin') or '未標示'}。",
            ]
        )
    if shot_event:
        lines.append(f"上一桿結果線索：{shot_event.get('pocket_result') or '未明確'}。")
    return (
        "請先根據 YOLO 辨識後的球局摘要判斷，再交由 Gemma 產生一段產品化擊球建議。"
        "如果路線規劃為空，但 YOLO 語意有效，必須用合法目標、袋口清線與阻擋資訊回答，不可套用固定保守模板。"
        "格式必須是純文字 2 到 3 句，依序包含：判斷原因、具體做法、這樣做的目的。"
        "禁止輸出 Markdown、標籤、FPS、VRAM、Coordinates、Deviation、座標、原始資料、debug 或內部欄位字樣。"
        "最終輸出不要提 YOLO、planner、JSON 或資料不足。"
        "如果玩家指定的袋口和目前清線袋口不同，要直接說不建議，並說明球路原因與替代打法。"
        "\n目前盤面資訊：\n"
        + "\n".join(lines)
    )


def _call_vllm_action_suggestion(context: dict[str, Any], locale: str = "zh-TW") -> str:
    """Call Gemma/vLLM for action suggestions. No local fallback is allowed."""
    payload = {
        "model": AI_COACH_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 CueVex 的專業數據導師。只輸出行動導向擊球建議，"
                    "語氣簡潔精準，但必須說明為什麼這樣做。"
                    f"{_locale_instruction(locale)}"
                ),
            },
            {"role": "user", "content": _build_action_suggestion_prompt(context)},
        ],
        "temperature": 0.45,
        "top_p": 0.9,
        "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 180),
    }
    raw = _complete_vllm_payload(payload).strip()
    if not raw:
        raise RuntimeError("vLLM returned empty action suggestion")
    return _clean_action_suggestion(raw)


def _social_prompt(route: str, message: str, locale: str) -> list[dict[str, str]]:
    """Build a persona-only prompt that intentionally excludes table-analysis data."""
    route_guidance = {
        "social_greeting": "使用者在打招呼。親切自然回應，可輕輕邀請開始訓練，但不要固定句。",
        "social_private": "使用者問私人或玩笑問題。幽默化解，可用撞球梗或中二梗帶過，避免冒犯。",
        "social_identity": "使用者分享身分或性向。尊重、接納，不說教，不分析球桌，可自然引導回訓練。",
        "social_romance": "使用者提出戀愛或曖昧話題。溫和設界線，用撞球梗幽默帶回球賽。",
        "social_mood": "使用者心情低落或覺得打不好。先同理與鼓勵，不做技術分析，可給一個簡短心態建議。",
        "social_goodbye": "使用者結束對話。自然道別，可簡短期待下次進步。",
    }.get(route, "一般日常對話。維持 CueVex 專業教練人格，自然回覆。")
    system = (
        "你是 CueVex 的 AI 撞球教練。你專業、親切、幽默但不油膩。"
        "這是一段社交或日常對話，不可使用 YOLO、planner、球路、FPS 或任何技術分析資料。"
        "不要輸出完整擊球分析，不要列目標球/袋、力道、桿法、風險。"
        "回答 1 到 2 句即可，繁體中文。"
        "若使用者談性向或身分，尊重接納，不嘲笑、不評判。"
        "若使用者挑釁或開玩笑，保持教練風度，用撞球梗輕輕帶過。"
        f"{_locale_instruction(locale)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"情境：{route_guidance}\n使用者：{message}"},
    ]


def _call_vllm_social(message: str, route: str, locale: str = "zh-TW") -> str:
    """Call Gemma/vLLM for social chat without passing any recognition data."""
    payload = {
        "model": AI_COACH_MODEL,
        "messages": _social_prompt(route, message, locale),
        "temperature": 0.85,
        "top_p": 0.95,
        "max_tokens": min(max(AI_COACH_MAX_TOKENS, 80), 140),
    }
    return _clean_recommendation(_complete_vllm_payload(payload))


def _non_visual_prompt(route: str, message: str, locale: str) -> list[dict[str, str]]:
    return _non_visual_prompt_with_context(route, message, {}, locale)


def _format_conversation_context(context: dict[str, Any]) -> str:
    conversation = context.get("conversation_context") if isinstance(context.get("conversation_context"), dict) else {}
    recent = conversation.get("recent_messages") if isinstance(conversation.get("recent_messages"), list) else []
    if not recent:
        return "近期對話：無。"
    lines: list[str] = []
    for item in recent[-20:]:
        if not isinstance(item, dict):
            continue
        role = "玩家" if item.get("role") == "player" else "教練"
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(f"{role}: {text[:500]}")
    follow = "是" if conversation.get("possible_follow_up") else "否"
    last_user = str(conversation.get("last_user_question") or "").strip()
    last_coach = str(conversation.get("last_coach_answer") or "").strip()
    return "\n".join([
        "近期對話：",
        *lines,
        f"可能是追問：{follow}",
        f"上一個玩家問題：{last_user[:500] if last_user else '無'}",
        f"上一個教練回答：{last_coach[:700] if last_coach else '無'}",
    ])


def _conversation_history_messages(context: dict[str, Any], current_message: str) -> list[dict[str, str]]:
    conversation = context.get("conversation_context") if isinstance(context.get("conversation_context"), dict) else {}
    recent = conversation.get("recent_messages") if isinstance(conversation.get("recent_messages"), list) else []
    messages: list[dict[str, str]] = []
    for item in recent[-20:]:
        if not isinstance(item, dict):
            continue
        role = "user" if item.get("role") == "player" else "assistant"
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if role == "user" and text == current_message and item is recent[-1]:
            continue
        messages.append({"role": role, "content": text[:1000]})
    return messages


def _non_visual_prompt_with_context(route: str, message: str, context: dict[str, Any], locale: str) -> list[dict[str, str]]:
    route_guidance = {
        "social_greeting": "使用者在打招呼。自然回應，可邀請開始訓練，但不要固定句。",
        "social_private": "使用者問私人或玩笑問題。可用撞球梗幽默化解，例如感情線會打歪，但避免冒犯。",
        "social_identity": "使用者分享身分或性向。尊重接納，不評判，可自然帶回球桌。",
        "social_romance": "使用者提出戀愛或曖昧話題。溫和設界線，用撞球梗帶回球賽。",
        "social_mood": "使用者心情低落或覺得打不好。先同理，不做畫面分析，可給一個短心態建議。",
        "social_goodbye": "使用者結束對話。自然道別。",
        "rule_support": "使用者問撞球或九號球規則。直接回答規則，保持教練口吻。",
        "knowledge_support": "使用者問撞球知識、選手或常識。直接回答，不依賴當前畫面。",
        "ui_support": "使用者問 CueVex 系統操作、設定、帳號、回放、校正或介面問題。依系統操作手冊推測最可能位置。",
        "non_visual_chat": "非當前畫面問題。回答使用者本身，不要求指定目標球或袋口。",
    }.get(route, "非當前畫面問題。回答使用者本身，不要求指定目標球或袋口。")
    system = (
        "你是 CueVex 的 AI 撞球教練。你專業、親切、偶爾幽默，但回答要精準。"
        "這不是當前球桌畫面分析，不可使用或要求 YOLO、planner、shot_event、FPS、座標、球路資料。"
        "不要說資料不足，不要要求玩家指定目標球或袋口，除非玩家明確在問當前球路。"
        "你會收到近期對話。若玩家用短句追問，例如「台灣呢」「那個怎麼設定」「剛剛為什麼」，請先根據近期對話補全問題再回答。"
        "不要要求玩家重問完整句；如果上下文不足，先照最可能意思回答，再自然請玩家補一個關鍵字。"
        "可以用撞球比喻或撞球梗，但不可假裝已經看到目前畫面。"
        "系統操作、設定、帳號問題必須依下方 CueVex 系統操作手冊回答；玩家用詞和系統名稱不同時，請猜最可能的功能位置。"
        "系統操作問題要優先回答去哪裡設定，不要只推薦顏色或風格。"
        "禁止輸出 Markdown、方括號標籤或 [emerald] 這類前端標籤。"
        "一般回答 1 到 3 句，不要過度條列。"
        f"{_locale_instruction(locale)}\n\n{SYSTEM_OPERATION_MANUAL}"
    )
    history_messages = _conversation_history_messages(context, message)
    return [
        {"role": "system", "content": system},
        *history_messages,
        {"role": "user", "content": f"情境：{route_guidance}\n對話摘要：\n{_format_conversation_context(context)}\n目前使用者：{message}"},
    ]


def _call_vllm_non_visual(message: str, route: str, context: dict[str, Any] | None = None, locale: str = "zh-TW") -> str:
    context = context if isinstance(context, dict) else {}
    payload = {
        "model": AI_COACH_MODEL,
        "messages": _non_visual_prompt_with_context(route, message, context, locale),
        "temperature": 0.75,
        "top_p": 0.92,
        "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 220),
    }
    return _clean_recommendation(_complete_vllm_payload(payload))


def _social_fallback_reply(route: str) -> str:
    """Fallback only when Gemma is unavailable; never includes table analysis."""
    replies = {
        "social_greeting": "我在，今天先用輕鬆節奏開局。你想暖手還是聊一下今天的狀態？",
        "social_private": "這題我先打安全球：我的私生活很單純，主要跟物理法則長期合作。",
        "social_identity": "收到，謝謝你直接說。回到球桌上，我只看你的節奏、專注和下一次出桿。",
        "social_romance": "這條線我先不進攻，戀愛交給真人；我可以陪你把球桌上的走位打得漂亮一點。",
        "social_mood": "手感差的日子很正常，先別急著否定自己。下一桿只抓一件事：出桿穩住。",
        "social_goodbye": "好，今天先收桿。下次回來，我們再把節奏慢慢調順。",
    }
    return replies.get(route, "我在，先不看數據。你想聊狀態，還是等一下再回到訓練？")


def _non_visual_fallback_reply(route: str, message: str) -> str:
    return "Gemma 暫時沒有回應，我先不套用固定答案。等模型恢復後再問一次，我會依照你的問題自然回答。"


def _is_non_visual_context(context: dict[str, Any]) -> bool:
    request = context.get("request") if isinstance(context.get("request"), dict) else {}
    if str(request.get("intent") or "").strip() == "non_analysis":
        return True
    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    return str(semantic_context.get("reason") or "").strip() == "NON_ANALYSIS_CHAT"


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
            cleaned = cleaned[len(prefix) :].strip()
            break
    cleaned = _strip_answer_preface(cleaned)
    return cleaned


def _strip_answer_preface(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = (
        r"^根據你(?:詢問|問)的(?:規則)?問題[，,：:\s]*",
        r"^根據您的(?:詢問|問題)[，,：:\s]*",
        r"^根據(?:九號球|Nine\s*ball|9\s*ball).*?(?:定義如下|如下)[：:\s]*",
        r"^.*?的定義如下[：:\s]*",
        r"^定義如下[：:\s]*",
    )
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned.startswith("合法碰球定義："):
        cleaned = "合法碰球是" + cleaned[len("合法碰球定義：") :].lstrip()
    return cleaned


def _context_dict(context: dict[str, Any], key: str) -> dict[str, Any]:
    value = context.get(key) if isinstance(context, dict) else None
    if isinstance(value, dict):
        return value
    nested = context.get("context") if isinstance(context, dict) else None
    value = nested.get(key) if isinstance(nested, dict) else None
    return value if isinstance(value, dict) else {}


def _analytics_context(context: dict[str, Any]) -> dict[str, Any]:
    return _context_dict(context, "analytics_context")


def _is_analytics_context(context: dict[str, Any]) -> bool:
    request = _context_dict(context, "request")
    if str(request.get("intent") or "").strip() == "analytics_advice":
        return True
    if str(request.get("response_mode") or "").strip() == "analytics_advice":
        return True
    analytics = _analytics_context(context)
    return str(analytics.get("schema_version") or "").strip() == "coach.analytics_context.v1"


def _format_rate_value(value: Any) -> str:
    if value is None:
        return "無"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if 0 <= number <= 1:
        return f"{round(number * 100)}%"
    return f"{round(number, 1)}"


def _analytics_empty_reply(context: dict[str, Any]) -> str:
    analytics = _analytics_context(context)
    player = str(analytics.get("player") or "目前帳號").strip()
    return (
        f"{player} 目前可分析資料還少，還不足以判斷穩定弱點或趨勢。"
        "先完成幾次練習或對戰，讓系統累積出桿事件與練習紀錄；下一步建議從直球準度和定點停球各練 10 分鐘開始。"
    )


def _analytics_fallback_reply(context: dict[str, Any]) -> str:
    analytics = _analytics_context(context)
    if not analytics.get("has_data"):
        return _analytics_empty_reply(context)
    player_stats = analytics.get("player_stats") if isinstance(analytics.get("player_stats"), dict) else {}
    overview = analytics.get("overview") if isinstance(analytics.get("overview"), dict) else {}
    mobile = analytics.get("mobile_analytics_v1") if isinstance(analytics.get("mobile_analytics_v1"), dict) else {}
    weakest = str(mobile.get("weakest_ability") or "目前弱項").strip()
    strongest = str(mobile.get("strongest_ability") or "目前強項").strip()
    trainings = mobile.get("recommended_trainings") if isinstance(mobile.get("recommended_trainings"), list) else []
    first_training = trainings[0] if trainings and isinstance(trainings[0], dict) else {}
    training_title = str(first_training.get("title") or "定點停球訓練").strip()
    total_practice = int(player_stats.get("total_practice_sessions") or 0)
    total_games = int(player_stats.get("total_games") or 0)
    pocket_rate = _format_rate_value(overview.get("pocket_rate"))
    return (
        f"目前資料顯示你累積 {total_practice} 次練習、{total_games} 場對戰，進球率約 {pocket_rate}。"
        f"{strongest}相對穩，但{weakest}是下一個優先加強點。"
        f"下一步先做「{training_title}」10 到 12 分鐘，重點放在固定出桿節奏與母球停位。"
    )


def _build_analytics_advice_prompt(context: dict[str, Any], message: str, locale: str) -> str:
    analytics = _analytics_context(context)
    if not analytics:
        return "目前沒有數據語境。請用繁體中文說明需要先累積練習或對戰資料。"

    player_stats = analytics.get("player_stats") if isinstance(analytics.get("player_stats"), dict) else {}
    overview = analytics.get("overview") if isinstance(analytics.get("overview"), dict) else {}
    offense = analytics.get("offense") if isinstance(analytics.get("offense"), dict) else {}
    trends = analytics.get("trends") if isinstance(analytics.get("trends"), dict) else {}
    trend_summary = analytics.get("trend_summary") if isinstance(analytics.get("trend_summary"), dict) else {}
    mobile = analytics.get("mobile_analytics_v1") if isinstance(analytics.get("mobile_analytics_v1"), dict) else {}
    return (
        "任務：根據 CueVex 資料庫統計回答玩家的數據問題。"
        "這不是目前球桌畫面分析，不可提 YOLO、planner、座標、debug、原始 JSON 或資料庫欄位名。"
        "若 has_data=false，必須明確說目前可分析資料還少，建議先完成練習或對戰累積 shot events / practice records，不可捏造弱點。"
        "若 has_data=true，回答 2 到 4 句，必須引用至少一個實際數字或弱點，並給一個下一步訓練建議。"
        "輸出自然口語，不要 Markdown，不要條列。"
        f"{_locale_instruction(locale)}\n"
        f"玩家問題：{message}\n"
        f"玩家：{analytics.get('player') or '未知'}；範圍：{analytics.get('range') or 'week'}；是否有資料：{analytics.get('has_data')}。\n"
        f"玩家統計摘要：{_short_json(player_stats, limit=900)}\n"
        f"總覽摘要：{_short_json(overview, limit=900)}\n"
        f"進攻摘要：{_short_json(offense, limit=900)}\n"
        f"趨勢摘要：{_short_json(trends, limit=700)}\n"
        f"趨勢變化：{_short_json(trend_summary, limit=320)}\n"
        f"手機能力摘要：{_short_json(mobile, limit=900)}\n"
    )[:AI_COACH_MAX_PROMPT_CHARS]


def _call_vllm_analytics_advice(message: str, context: dict[str, Any], locale: str = "zh-TW") -> str:
    if not _analytics_context(context).get("has_data"):
        return _analytics_empty_reply(context)
    payload = {
        "model": AI_COACH_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 CueVex 的數據型撞球教練。你只根據資料庫統計回答，"
                    "要把數字轉成玩家聽得懂的弱點與訓練方向。"
                    f"{_locale_instruction(locale)}"
                ),
            },
            {"role": "user", "content": _build_analytics_advice_prompt(context, message, locale)},
        ],
        "temperature": 0.45,
        "top_p": 0.9,
        "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 220),
    }
    reply = _clean_recommendation(_complete_vllm_payload(payload))
    return reply or _analytics_fallback_reply(context)


def _technical_result(
    recommendation: str,
    *,
    source: str,
    start: float,
    locale: str,
    confidence: float = 0.95,
    semantic: str = "",
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "semantic_description": semantic,
        "recommendation": recommendation,
        "locale": locale,
        "confidence": confidence,
        "processing_time": round(time.time() - start, 3),
        "error": None,
        "source": source,
    }


def _system_status_reply(context: dict[str, Any]) -> str:
    status = _context_dict(context, "system_status")
    yolo_status = str(status.get("yolo_status") or "online").lower()
    if yolo_status == "offline":
        return "偵測系統暫時斷開了，請檢查後端連線或重啟服務。"

    warnings: list[str] = []
    try:
        fps = float(status.get("fps"))
    except (TypeError, ValueError):
        fps = 0.0
    if 0 < fps < 15:
        warnings.append(f"目前 FPS 約 {fps:.1f}，環境可能過於複雜或硬體負荷偏重，辨識準確度可能會下降。")

    balls_outside_roi = status.get("balls_outside_roi")
    if isinstance(balls_outside_roi, list) and balls_outside_roi:
        warnings.append("有球看起來超出球桌 ROI。有球噴出去了嗎？或是 ROI 跑掉了？建議微調一下邊框。")

    lighting_status = str(status.get("lighting_status") or "normal").lower()
    if lighting_status in {"too_dark", "too_bright"}:
        warnings.append("目前光線狀態不太理想，可能影響顏色辨識。建議檢查球館燈光，或進入「顏色校正」重新掃描。")

    detected_count = status.get("detected_count")
    if not warnings:
        count_text = f"目前辨識到 {detected_count} 顆球，" if detected_count is not None else ""
        fps_text = f"FPS 約 {fps:.1f}，" if fps > 0 else ""
        return f"{count_text}{fps_text}偵測狀態看起來正常。"
    return "\n".join(warnings)


def _soft_no_table_context_reply() -> str:
    return "我現在還看不到穩定的檯面路線，先不要硬攻。用中桿小力找最低號球的合法碰球，讓母球停在檯面中區，等畫面與路線穩定後再挑進攻袋口。"


def _ui_support_reply(message: str, context: dict[str, Any]) -> str:
    ui_context = _context_dict(context, "ui_context")
    text = str(message or "")
    auth_type = str(ui_context.get("auth_type") or ui_context.get("type") or "").lower()

    if re.search(r"(球桌邊框|球桌边框|桌面邊框|桌面边框|球桌邊界|球桌边界|桌面邊界|桌面边界|球桌範圍|球桌范围|桌面範圍|桌面范围|邊框|边框|roi|ROI|四點|四点|調整球桌|调整球桌|調整桌面|调整桌面|去哪裡調整|去哪里调整)", text, re.IGNORECASE):
        return "到「設定 > 球桌校正 > ROI 微調 / 微調邊框」設定。"

    if re.search(r"(顏色|颜色|好看|翡翠綠|翡翠绿|美感|配色|ui|介面|界面|外觀|外观|主題|主题|強調色|强调色)", text, re.IGNORECASE):
        return "到「設定 > 外觀 > 介面 > 介面主題、強調色」設定。"

    if re.search(r"(存不了|保存|儲存|储存|sqlite|設定|设置)", text, re.IGNORECASE):
        if auth_type == "guest":
            return "到「設定 > 帳號管理」登入；訪客模式可以使用主程式，但個人設定與對話紀錄要登入後才會寫入 SQLite 帳號資料庫。"
        return "到「設定 > 一般」儲存設定；你已經是登入狀態，若仍無法保存，請重新整理頁面後再試。"

    return "到「設定」查看相關項目。"


def _rule_support_reply(message: str) -> str:
    text = str(message or "")
    if re.search(r"(合法碰球|合法撞球|合法擊球)", text, re.IGNORECASE):
        return "合法碰球是在九號球中，母球必須先碰到檯面上號碼最小的目標球。若先碰到其他球、沒有碰到任何球，或擊球後沒有任何球進袋且沒有球碰到顆星，通常會被判犯規。"
    if re.search(r"(犯規|foul)", text, re.IGNORECASE):
        return "九號球常見犯規包含：母球未先碰到最低號目標球、母球洗袋、擊球後沒有球進袋也沒有球碰到顆星、球跳離球桌，或出桿時連擊。犯規後通常由對手取得自由球。"
    return "九號球的核心規則是每次出桿都要先碰檯面上號碼最小的球，但不一定要打進最低號球；只要合法碰球後讓任一目標球進袋，就可以繼續出桿。"


def _knowledge_support_reply(message: str) -> str:
    text = str(message or "").lower()
    if any(keyword in text for keyword in ("斯諾克", "斯诺克", "snooker")):
        return "斯諾克領域常被提到的名將有 Ronnie O'Sullivan、Stephen Hendry、Steve Davis、Mark Selby 和 Judd Trump；如果你想看母球控制與長台準度，O'Sullivan 和 Selby 很值得研究。"
    return "撞球界常被提到的選手有 Efren Reyes、Shane Van Boening、Earl Strickland、Francisco Bustamante 和 Ko Pin Yi。新手可以先看 Efren Reyes 的走位與解球，他的選擇很像在提前三桿布局。"


def _post_shot_analysis_reply(context: dict[str, Any]) -> str:
    shot = _context_dict(context, "shot_event")
    if not shot:
        return "我現在還看不到完整擊球結果，先用保守打法處理：下一桿放慢節奏，確認瞄準線與出桿直線，再讓母球自然推出去。"

    pocket_result = str(shot.get("pocket_result") or "").lower()
    potted_balls = shot.get("potted_balls") if isinstance(shot.get("potted_balls"), list) else []
    made = pocket_result in {"made", "potted", "success", "in"} or bool(potted_balls)
    result_text = (
        f"結果判定：{'[emerald]進球成功[/emerald]' if made else '這桿沒有進球'}"
        f"{'，進球：' + ', '.join(f'#{ball}' for ball in potted_balls) if potted_balls else ''}。"
    )

    diagnosis: list[str] = []
    try:
        actual = float(shot.get("impact_angle"))
        ideal = float(shot.get("ideal_angle"))
        angle_delta = actual - ideal
    except (TypeError, ValueError):
        angle_delta = None

    if angle_delta is not None:
        abs_delta = abs(angle_delta)
        # Deviation % = abs(theta_actual - theta_ideal) / Ball_Diameter * 100%.
        # 這裡用偏差百分比作為語氣權重：偏差越大，診斷越直接；偏差小則偏鼓勵。
        ball_diameter = float(shot.get("ball_diameter") or 57.2)
        deviation_pct = abs_delta / max(ball_diameter, 1.0) * 100.0
        if abs_delta > 5:
            thickness = "打太厚" if angle_delta > 0 else "打太薄"
            tone = "明顯" if deviation_pct >= 14 else "有一點"
            diagnosis.append(f"撞擊角偏差 {abs_delta:.1f} 度，{tone}{thickness}。")
        else:
            diagnosis.append(f"撞擊角偏差約 {abs_delta:.1f} 度，方向控制算穩。")

    try:
        velocity_change = float(shot.get("velocity_change"))
    except (TypeError, ValueError):
        velocity_change = 0.0
    if abs(velocity_change) >= 0.35:
        diagnosis.append("速度損耗偏大，主要問題在力道控制（Speed Control）。")
    elif velocity_change:
        diagnosis.append("速度變化在可控範圍，節奏可以維持。")

    if not diagnosis:
        diagnosis.append("目前可判讀的擊球細節不多，先以結果與穩定出桿為主。")

    advice: list[str] = []
    if angle_delta is not None and abs(angle_delta) > 5:
        advice.append("下一桿先修正切球厚度，瞄準點微調半顆球以內。")
    if abs(velocity_change) >= 0.35:
        advice.append("力道先減輕約 15%，讓母球多靠自然滾動完成走位。")
    if not advice:
        advice.append("下一桿維持同樣節奏，把收桿停穩，讓準度繼續累積。")

    return "\n".join([
        result_text,
        f"物理診斷：{' '.join(diagnosis)}",
        f"具體建議：{' '.join(advice)}",
    ])


async def _coach_result(message: str, context: dict[str, Any], locale: str = "zh-TW") -> dict[str, Any]:
    """Generate one coach result for chat or explicit suggestion requests."""
    locale = _normalize_locale(locale)
    start = time.time()
    route = ConversationRouter.route(message)
    if _is_analytics_context(context):
        try:
            reply = await asyncio.to_thread(_call_vllm_analytics_advice, message, context, locale)
            error = None
        except Exception as exc:
            reply = _analytics_fallback_reply(context)
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": "",
            "recommendation": reply,
            "locale": locale,
            "confidence": 0.9 if error is None else 0.55,
            "processing_time": round(time.time() - start, 3),
            "error": None,
            "source": "analytics_advice" if error is None else "analytics_advice_fallback",
        }
    if _is_non_visual_context(context) and not (
        ConversationRouter.is_social(route) or route in {"rule_support", "knowledge_support", "ui_support"}
    ):
        route = "non_visual_chat"
    non_visual_routes = {"rule_support", "knowledge_support", "ui_support"}
    if ConversationRouter.is_social(route) or route in non_visual_routes or _is_non_visual_context(context):
        try:
            reply = await asyncio.to_thread(_call_vllm_non_visual, message, route, context, locale)
            error = None
        except Exception as exc:
            reply = _non_visual_fallback_reply(route, message)
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": "",
            "recommendation": reply,
            "locale": locale,
            "confidence": 0.9 if error is None else 0.45,
            "processing_time": round(time.time() - start, 3),
            "error": None,
            "source": "non_visual_chat" if error is None else f"{route}_fallback",
        }

    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    if not semantic_context and isinstance(context.get("context"), dict):
        nested = context["context"].get("semantic_context")
        semantic_context = nested if isinstance(nested, dict) else {}

    if not semantic_context:
        semantic_context = {
            "valid": False,
            "reason": "NO_SEMANTIC_CONTEXT",
            "summary": "未提供語意資料",
        }
    context = {**context, "semantic_context": semantic_context}

    semantic = _semantic_description(semantic_context)
    if _is_action_suggestion_request(context):
        try:
            recommendation = await asyncio.to_thread(_call_vllm_action_suggestion, context, locale)
            error = None
        except Exception as exc:
            recommendation = ""
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": semantic,
            "recommendation": recommendation,
            "locale": locale,
            "confidence": 0.9 if recommendation else 0.0,
            "processing_time": round(time.time() - start, 3),
            "error": error,
            "source": "action_suggestion" if recommendation else "action_suggestion_error",
        }

    system_reply = _system_status_reply(context)
    system_status = _context_dict(context, "system_status")
    try:
        system_fps = float(system_status.get("fps"))
    except (TypeError, ValueError):
        system_fps = 0.0
    if system_reply and (
        route == "system_status"
        or str(system_status.get("yolo_status") or "").lower() == "offline"
        or 0 < system_fps < 15
        or system_status.get("balls_outside_roi")
        or str(system_status.get("lighting_status") or "normal").lower() in {"too_dark", "too_bright"}
    ):
        return _technical_result(system_reply, source="system_status", start=start, locale=locale, semantic=semantic)

    if route == "shot_analysis":
        return _technical_result(
            _post_shot_analysis_reply(context),
            source="post_shot_analysis",
            start=start,
            locale=locale,
            semantic=semantic,
            confidence=0.92,
        )

    request_type = _request_type(context)
    if locale == "zh-TW" and request_type in {"suggest", "analysis"} and _is_suggestion_request(message, context):
        recommendation = _deterministic_route_reply(context)
        if recommendation:
            return {
                "timestamp": datetime.now().isoformat(),
                "semantic_description": semantic,
                "recommendation": recommendation,
                "locale": locale,
                "confidence": 0.9,
                "processing_time": round(time.time() - start, 3),
                "error": None,
                "source": "planner",
            }

    try:
        recommendation = await asyncio.to_thread(_call_vllm, message, context, semantic, locale)
        error = None
    except Exception as exc:
        recommendation = ""
        error = str(exc)

    return {
        "timestamp": datetime.now().isoformat(),
        "semantic_description": semantic,
        "recommendation": recommendation,
        "locale": locale,
        "confidence": 0.8 if recommendation else 0.0,
        "processing_time": round(time.time() - start, 3),
        "error": error,
    }


async def _send_coach_delta(websocket: WebSocket, request_id: str, delta: str) -> None:
    await websocket.send_text(
        json.dumps(
            {
                "type": "coach.delta",
                "request_id": request_id,
                "status": "streaming",
                "payload": {"delta": delta},
            },
            ensure_ascii=False,
        )
    )


async def _stream_vllm_payload_to_ws(websocket: WebSocket, request_id: str, payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for chunk in _iter_vllm_payload_chunks(payload):
        chunks.append(chunk)
        await _send_coach_delta(websocket, request_id, chunk)
        await asyncio.sleep(0)
    return "".join(chunks).strip()


async def _coach_result_stream(
    websocket: WebSocket,
    request_id: str,
    message: str,
    context: dict[str, Any],
    locale: str = "zh-TW",
) -> dict[str, Any]:
    """Generate one coach result while forwarding vLLM token deltas."""
    if not AI_COACH_STREAMING_ENABLED:
        return await _coach_result(message, context, locale)

    locale = _normalize_locale(locale)
    start = time.time()
    route = ConversationRouter.route(message)
    if _is_analytics_context(context):
        if not _analytics_context(context).get("has_data"):
            reply = _analytics_empty_reply(context)
            return {
                "timestamp": datetime.now().isoformat(),
                "semantic_description": "",
                "recommendation": reply,
                "locale": locale,
                "confidence": 0.8,
                "processing_time": round(time.time() - start, 3),
                "error": None,
                "source": "analytics_advice_empty",
            }
        payload = {
            "model": AI_COACH_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 CueVex 的數據型撞球教練。你只根據資料庫統計回答，"
                        "要把數字轉成玩家聽得懂的弱點與訓練方向。"
                        f"{_locale_instruction(locale)}"
                    ),
                },
                {"role": "user", "content": _build_analytics_advice_prompt(context, message, locale)},
            ],
            "temperature": 0.45,
            "top_p": 0.9,
            "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 220),
        }
        try:
            reply = _clean_recommendation(await _stream_vllm_payload_to_ws(websocket, request_id, payload))
            error = None
        except Exception as exc:
            reply = _analytics_fallback_reply(context)
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": "",
            "recommendation": reply or _analytics_fallback_reply(context),
            "locale": locale,
            "confidence": 0.9 if error is None else 0.55,
            "processing_time": round(time.time() - start, 3),
            "error": None,
            "source": "analytics_advice" if error is None else "analytics_advice_fallback",
        }
    if _is_non_visual_context(context) and not (
        ConversationRouter.is_social(route) or route in {"rule_support", "knowledge_support", "ui_support"}
    ):
        route = "non_visual_chat"
    non_visual_routes = {"rule_support", "knowledge_support", "ui_support"}
    if ConversationRouter.is_social(route) or route in non_visual_routes or _is_non_visual_context(context):
        payload = {
            "model": AI_COACH_MODEL,
            "messages": _non_visual_prompt_with_context(route, message, context, locale),
            "temperature": 0.75,
            "top_p": 0.92,
            "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 220),
        }
        try:
            reply = _clean_recommendation(await _stream_vllm_payload_to_ws(websocket, request_id, payload))
            error = None
        except Exception as exc:
            reply = _non_visual_fallback_reply(route, message)
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": "",
            "recommendation": reply,
            "locale": locale,
            "confidence": 0.9 if error is None else 0.45,
            "processing_time": round(time.time() - start, 3),
            "error": None,
            "source": "non_visual_chat" if error is None else f"{route}_fallback",
        }

    semantic_context = context.get("semantic_context") if isinstance(context.get("semantic_context"), dict) else {}
    if not semantic_context and isinstance(context.get("context"), dict):
        nested = context["context"].get("semantic_context")
        semantic_context = nested if isinstance(nested, dict) else {}
    if not semantic_context:
        semantic_context = {
            "valid": False,
            "reason": "NO_SEMANTIC_CONTEXT",
            "summary": "目前沒有可用的球桌語意資料。",
        }
    context = {**context, "semantic_context": semantic_context}
    semantic = _semantic_description(semantic_context)

    if _is_action_suggestion_request(context):
        payload = {
            "model": AI_COACH_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "雿 CueVex ??璆剜??撣怒頛詨銵?撠???撱箄降嚗?"
                        "隤除蝪⊥?蝎暹?嚗?敹?隤芣??箔?暻潮見??"
                        f"{_locale_instruction(locale)}"
                    ),
                },
                {"role": "user", "content": _build_action_suggestion_prompt(context)},
            ],
            "temperature": 0.45,
            "top_p": 0.9,
            "max_tokens": min(max(AI_COACH_MAX_TOKENS, 120), 180),
        }
        try:
            raw = await _stream_vllm_payload_to_ws(websocket, request_id, payload)
            recommendation = _clean_action_suggestion(raw) if raw else ""
            error = None if recommendation else "vLLM returned empty action suggestion"
        except Exception as exc:
            recommendation = ""
            error = str(exc)
        return {
            "timestamp": datetime.now().isoformat(),
            "semantic_description": semantic,
            "recommendation": recommendation,
            "locale": locale,
            "confidence": 0.9 if recommendation else 0.0,
            "processing_time": round(time.time() - start, 3),
            "error": error,
            "source": "action_suggestion" if recommendation else "action_suggestion_error",
        }

    system_reply = _system_status_reply(context)
    system_status = _context_dict(context, "system_status")
    try:
        system_fps = float(system_status.get("fps"))
    except (TypeError, ValueError):
        system_fps = 0.0
    if system_reply and (
        route == "system_status"
        or str(system_status.get("yolo_status") or "").lower() == "offline"
        or 0 < system_fps < 15
        or system_status.get("balls_outside_roi")
        or str(system_status.get("lighting_status") or "normal").lower() in {"too_dark", "too_bright"}
    ):
        return _technical_result(system_reply, source="system_status", start=start, locale=locale, semantic=semantic)
    if route == "shot_analysis":
        return _technical_result(
            _post_shot_analysis_reply(context),
            source="post_shot_analysis",
            start=start,
            locale=locale,
            semantic=semantic,
            confidence=0.92,
        )

    request_type = _request_type(context)
    if locale == "zh-TW" and request_type in {"suggest", "analysis"} and _is_suggestion_request(message, context):
        recommendation = _deterministic_route_reply(context)
        if recommendation:
            return {
                "timestamp": datetime.now().isoformat(),
                "semantic_description": semantic,
                "recommendation": recommendation,
                "locale": locale,
                "confidence": 0.9,
                "processing_time": round(time.time() - start, 3),
                "error": None,
                "source": "planner",
            }

    payload = {
        "model": AI_COACH_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt(locale)},
            {"role": "user", "content": _build_prompt(message, context, semantic)},
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": AI_COACH_MAX_TOKENS,
    }
    try:
        recommendation = _clean_recommendation(await _stream_vllm_payload_to_ws(websocket, request_id, payload))
        error = None
    except Exception as exc:
        recommendation = ""
        error = str(exc)

    return {
        "timestamp": datetime.now().isoformat(),
        "semantic_description": semantic,
        "recommendation": recommendation,
        "locale": locale,
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
            locale = _normalize_locale(payload.get("locale"))

            if msg_type == "analysis.request":
                semantic_context = (
                    payload.get("semantic_context")
                    if isinstance(payload.get("semantic_context"), dict)
                    else {}
                )
                if not semantic_context.get("stable"):
                    continue
                result = await _coach_result("請根據目前桌面給出教練建議。", payload, locale)
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
                if payload.get("stream") is True:
                    result = await _coach_result_stream(websocket, request_id, chat_message, context, locale)
                else:
                    result = await _coach_result(chat_message, context, locale)
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
