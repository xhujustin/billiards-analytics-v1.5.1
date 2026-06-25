from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "architecture-images"
W, H = 1920, 1080

COLORS = {
    "bg": "#050505",
    "white": "#FAFAFA",
    "text": "#161616",
    "muted": "#5E5E5E",
    "orange": "#F58A1F",
    "orange_fill": "#F9E4D3",
    "blue": "#0C78CF",
    "blue_fill": "#DDF1FA",
    "purple": "#7A36C3",
    "purple_fill": "#F0D9F7",
    "green": "#08A86B",
    "green_fill": "#DDF3E9",
    "red": "#EF1E2D",
    "red_fill": "#F8C9CF",
    "gray": "#646464",
    "gray_fill": "#F0F0F0",
    "cyan": "#06AFC7",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\msjhbd.ttc" if bold else r"C:\Windows\Fonts\msjh.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(42, True)
F_SECTION = font(31, True)
F_BOX = font(23, True)
F_SMALL = font(19, False)
F_TINY = font(16, False)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    if not text:
        return 0, 0
    box = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=4)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> str:
    lines: list[str] = []
    for raw in text.split("\n"):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if text_size(draw, candidate, fnt)[0] <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return "\n".join(lines)


def canvas(title: str, color: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), COLORS["bg"])
    d = ImageDraw.Draw(img)
    tw, th = text_size(d, title, F_TITLE)
    d.text(((W - tw) / 2, 34), title, font=F_TITLE, fill=color)
    return img, d


def rounded(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    fill: str,
    outline: str,
    width: int = 3,
    radius: int = 18,
) -> None:
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def label(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    text: str,
    outline: str,
    fill: str = COLORS["white"],
    text_fill: str = COLORS["text"],
    fnt: ImageFont.ImageFont = F_BOX,
    width: int = 3,
    radius: int = 13,
) -> None:
    rounded(d, xy, fill, outline, width=width, radius=radius)
    wrapped = wrap(d, text, fnt, xy[2] - xy[0] - 28)
    tw, th = text_size(d, wrapped, fnt)
    d.multiline_text(
        ((xy[0] + xy[2] - tw) / 2, (xy[1] + xy[3] - th) / 2 - 2),
        wrapped,
        font=fnt,
        fill=text_fill,
        align="center",
        spacing=4,
    )


def section_title(d: ImageDraw.ImageDraw, text: str, xy: tuple[int, int, int, int], color: str) -> None:
    tw, _ = text_size(d, text, F_SECTION)
    d.text(((xy[0] + xy[2] - tw) / 2, xy[1] + 18), text, font=F_SECTION, fill=color)


def arrow(
    d: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    width: int = 4,
    dashed: bool = False,
) -> None:
    x1, y1 = start
    x2, y2 = end
    if dashed:
        dash_line(d, start, end, color, width)
    else:
        d.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 15
    p1 = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
    p2 = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
    d.polygon([end, p1, p2], fill=color)


def poly_arrow(d: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, width: int = 4, dashed: bool = False) -> None:
    for a, b in zip(points, points[1:]):
        last = b == points[-1]
        if last:
            arrow(d, a, b, color, width=width, dashed=dashed)
        elif dashed:
            dash_line(d, a, b, color, width)
        else:
            d.line((*a, *b), fill=color, width=width)


def dash_line(
    d: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    width: int = 3,
    dash: int = 16,
    gap: int = 10,
) -> None:
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    steps = int(dist // (dash + gap)) + 1
    ux, uy = dx / dist, dy / dist
    pos = 0
    for _ in range(steps):
        end_pos = min(pos + dash, dist)
        d.line((x1 + ux * pos, y1 + uy * pos, x1 + ux * end_pos, y1 + uy * end_pos), fill=color, width=width)
        pos += dash + gap


def legend(d: ImageDraw.ImageDraw, x: int, y: int, items: Iterable[tuple[str, str]]) -> None:
    items = list(items)
    height = 58 + len(items) * 28
    rounded(d, (x, y, x + 420, y + height), "#111111", COLORS["gray"], width=2, radius=10)
    d.text((x + 26, y + 18), "Flow Legend", font=F_SMALL, fill=COLORS["white"])
    offset = y + 56
    for color, text in items:
        d.line((x + 28, offset + 10, x + 98, offset + 10), fill=color, width=5)
        d.text((x + 112, offset), text, font=F_TINY, fill=COLORS["white"])
        offset += 26


def save(img: Image.Image, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / name)


def backend_flow() -> None:
    img, d = canvas("CueVex Backend Architecture Flow — Desktop FastAPI Runtime", COLORS["orange"])
    main = (250, 115, 1675, 1000)
    rounded(d, main, COLORS["orange_fill"], COLORS["orange"], width=4, radius=20)
    section_title(d, "Backend Core Runtime", main, COLORS["orange"])

    # External clients
    label(d, (35, 225, 210, 435), "Frontend Web\nREST API\nWebSocket Metadata\nMJPEG Stream", COLORS["blue"], COLORS["blue_fill"], fnt=F_SMALL)
    label(d, (1705, 225, 1885, 390), "AI Coach Service\n/ws/coach\ninternal channel", COLORS["red"], COLORS["red_fill"], fnt=F_SMALL)
    label(d, (1705, 470, 1885, 660), "Mobile / Cloud API\nAuth\nCommunity\nDashboard\nPush", COLORS["green"], COLORS["green_fill"], fnt=F_SMALL)
    label(d, (1705, 740, 1885, 920), "Cloud Services\nSupabase selected data\nExpo Push", COLORS["gray"], COLORS["gray_fill"], fnt=F_SMALL)

    # Main backend sections
    label(d, (300, 190, 550, 370), "Input Layer\nCamera / Video Source\nOpenCV Capture\nImage Processor", COLORS["orange"], fnt=F_SMALL)
    label(d, (610, 190, 910, 370), "Vision Runtime\nPoolTracker\nYOLO Detection\nTable ROI\nBall Color / Number", COLORS["orange"], fnt=F_SMALL)
    label(d, (950, 170, 1215, 245), "YOLO Weights\nmodel input", COLORS["orange"], fnt=F_SMALL)
    label(d, (970, 290, 1290, 455), "Runtime State Hub\nlatest_analysis_data\nRuntime Packet\nmetadata packet\nmulti_plan / planner_error", COLORS["orange"], fnt=F_SMALL)
    label(d, (1340, 205, 1600, 430), "FastAPI Service Layer\nREST API Routers\nWebSocket Metadata\nMJPEG Endpoints\nControl APIs", COLORS["orange"], fnt=F_SMALL)

    label(d, (300, 500, 560, 695), "Game / Practice Layer\nGameManager\nPractice Mode\nRule / Target State\nShot Event Detection", COLORS["orange"], fnt=F_SMALL)
    label(d, (635, 505, 920, 720), "Planning / AR / Calibration\nRoute Planner\nCalibration / ArUco\nProjector Renderer\nAR Metadata", COLORS["orange"], fnt=F_SMALL)
    label(d, (985, 520, 1265, 740), "Replay / Stats Layer\nRecordingManager\nLocal Artifacts\nSQLite recordings.db\nAnalytics Aggregation", COLORS["purple"], fnt=F_SMALL)
    label(d, (1320, 540, 1600, 760), "AI Coach Bridge Layer\nContext Router\nCoachPayloadBuilder\nCoachBridge\n/api/coach/chat/stream", COLORS["red"], fnt=F_SMALL)

    # Flow arrows
    arrow(d, (550, 280), (610, 280), COLORS["orange"])
    arrow(d, (910, 280), (970, 360), COLORS["orange"])
    arrow(d, (950, 210), (885, 245), COLORS["orange"])
    arrow(d, (1290, 360), (1340, 320), COLORS["orange"])
    arrow(d, (1120, 455), (795, 505), COLORS["orange"])
    arrow(d, (1080, 455), (1170, 520), COLORS["purple"])
    arrow(d, (1265, 640), (1320, 650), COLORS["red"])
    arrow(d, (1600, 650), (1705, 300), COLORS["red"])
    poly_arrow(d, [(1340, 320), (1340, 135), (230, 135), (210, 330)], COLORS["blue"])
    arrow(d, (1600, 320), (1705, 555), COLORS["green"])
    arrow(d, (1265, 720), (1705, 830), COLORS["gray"], dashed=True)
    arrow(d, (560, 600), (985, 610), COLORS["purple"])
    arrow(d, (920, 620), (985, 620), COLORS["purple"])
    legend(
        d,
        35,
        805,
        [
            (COLORS["blue"], "frontend output channels"),
            (COLORS["orange"], "backend runtime flow"),
            (COLORS["purple"], "analytics flow"),
            (COLORS["red"], "AI Coach bridge"),
            (COLORS["gray"], "selected cloud sync"),
        ],
    )
    save(img, "01_backend_architecture_flow.png")


def frontend_web() -> None:
    img, d = canvas("Frontend Web Architecture — Editable Components", COLORS["blue"])
    main = (35, 115, 1550, 1000)
    rounded(d, main, COLORS["blue_fill"], COLORS["blue"], width=4, radius=20)
    section_title(d, "Frontend Web Architecture", main, COLORS["blue"])
    label(d, (625, 175, 1060, 250), "Dashboard.tsx / React + Vite App Shell", COLORS["blue"], fnt=F_BOX)
    ui = (80, 300, 470, 900)
    rounded(d, ui, "#EAF7FC", COLORS["blue"], width=3)
    section_title(d, "UI Pages", ui, COLORS["blue"])
    y = 380
    for text, col in [
        ("Auth / Guest Gate", COLORS["blue"]),
        ("Live Stream / Monitor", COLORS["blue"]),
        ("Game / Practice", COLORS["blue"]),
        ("Replay / Stats", COLORS["purple"]),
        ("Settings / Camera / Calibration", COLORS["blue"]),
        ("AI Coach Chat", COLORS["red"]),
    ]:
        label(d, (125, y, 425, y + 62), text, col, fnt=F_SMALL)
        y += 78

    access = (520, 300, 1455, 900)
    rounded(d, access, "#EAF7FC", COLORS["blue"], width=3)
    section_title(d, "Client Access Layer", access, COLORS["blue"])
    label(d, (590, 390, 1390, 485), "Frontend Runtime Client", COLORS["blue"], fnt=F_BOX)
    x = 590
    for text in ["Session / Auth Client", "REST API Client", "WebSocket Control Client", "Metadata Buffer", "Connection Health"]:
        label(d, (x, 535, x + 155, 650), text, COLORS["blue"], fnt=F_TINY)
        x += 160
    label(d, (590, 720, 950, 835), "MJPEG Stream Viewer\n/stream/monitor\n/stream/projector", COLORS["orange"], fnt=F_SMALL)
    label(d, (1015, 720, 1390, 835), "AI Coach HTTP Stream Client\nPOST /api/coach/chat/stream", COLORS["red"], fnt=F_SMALL)

    backend = (1600, 190, 1885, 925)
    rounded(d, backend, COLORS["orange_fill"], COLORS["orange"], width=3)
    section_title(d, "Backend APIs", backend, COLORS["orange"])
    y = 300
    for text, col in [
        ("Auth / Session API", COLORS["orange"]),
        ("WebSocket / Metadata API", COLORS["blue"]),
        ("MJPEG Stream API", COLORS["orange"]),
        ("Replay / Stats REST API", COLORS["purple"]),
        ("Camera / Calibration REST API", COLORS["orange"]),
        ("AI Coach HTTP Bridge", COLORS["red"]),
    ]:
        label(d, (1640, y, 1845, y + 70), text, col, fnt=F_TINY)
        y += 90
    arrow(d, (1390, 430), (1600, 425), COLORS["blue"])
    arrow(d, (1390, 775), (1600, 805), COLORS["red"])
    poly_arrow(d, [(950, 775), (1510, 775), (1510, 515), (1600, 480)], COLORS["orange"])
    arrow(d, (475, 410), (590, 430), COLORS["blue"])
    arrow(d, (475, 645), (590, 775), COLORS["purple"])
    arrow(d, (475, 800), (1015, 790), COLORS["red"])
    arrow(d, (842, 390), (842, 250), "#D9D9D9")
    save(img, "02_frontend_web_architecture.png")


def replay_stats() -> None:
    img, d = canvas("Replay / Stats — Backend Subsystem", COLORS["purple"])
    runtime = (40, 260, 305, 900)
    rounded(d, runtime, COLORS["orange_fill"], COLORS["orange"], width=3)
    section_title(d, "Backend Runtime", runtime, COLORS["orange"])
    label(d, (85, 370, 260, 535), "Runtime Recording Inputs\nFrame snapshots\nShot events\nGame / practice metadata\nPlanner metadata", COLORS["orange"], fnt=F_TINY)
    label(d, (85, 680, 260, 790), "Clients\nFrontend Web\nMobile", COLORS["blue"], fnt=F_SMALL)

    sub = (360, 130, 1600, 980)
    rounded(d, sub, COLORS["purple_fill"], COLORS["purple"], width=4)
    section_title(d, "Replay / Stats Subsystem — inside Backend Core Runtime", sub, COLORS["purple"])
    label(d, (420, 250, 775, 465), "RecordingManager\ncreates recording session\nand writes artifacts", COLORS["purple"], fnt=F_BOX)
    label(d, (825, 250, 1190, 465), "Local Recording Files\nvideo.mp4\nthumbnail.jpg\nmetadata.json\nevents.json", COLORS["purple"], fnt=F_SMALL)
    label(d, (425, 560, 785, 780), "SQLite recordings.db\nrecordings\nshot_events\npractice_stats\nsync queue", COLORS["purple"], fnt=F_SMALL)
    label(d, (850, 560, 1190, 780), "Stats / Analytics Aggregation\nplayer\npractice\ngame\noffense\ncue control", COLORS["purple"], fnt=F_SMALL)
    label(d, (1240, 320, 1530, 780), "Replay API\nrecordings\nvideo\nthumbnail\nevents\nStats API\nAnalytics API", COLORS["purple"], fnt=F_SMALL)
    label(d, (630, 835, 1300, 935), "Supabase Sync\nselected analytics + social metadata only\nlocal video remains local", COLORS["blue"], fnt=F_SMALL)

    cloud = (1660, 330, 1900, 790)
    rounded(d, cloud, COLORS["gray_fill"], COLORS["gray"], width=3)
    section_title(d, "Cloud Services", cloud, COLORS["gray"])
    label(d, (1710, 460, 1850, 660), "Supabase\nProfiles\nSocial\nSelected analytics\nPush records", COLORS["gray"], fnt=F_SMALL)

    arrow(d, (305, 445), (420, 360), COLORS["orange"])
    arrow(d, (775, 360), (825, 360), COLORS["purple"])
    arrow(d, (600, 465), (600, 560), COLORS["green"])
    arrow(d, (785, 670), (850, 670), COLORS["purple"])
    arrow(d, (1190, 660), (1240, 560), COLORS["purple"])
    poly_arrow(d, [(260, 735), (330, 735), (330, 225), (1240, 540)], COLORS["orange"])
    arrow(d, (965, 835), (600, 780), COLORS["blue"], dashed=True)
    arrow(d, (1300, 885), (1660, 590), COLORS["blue"], dashed=True)
    save(img, "03_replay_stats_backend_subsystem.png")


def mobile_architecture() -> None:
    img, d = canvas("CueVex — PWA and Cloud Mobile API Architecture", COLORS["green"])

    pwa = (35, 120, 500, 925)
    rounded(d, pwa, COLORS["green_fill"], COLORS["green"], width=3)
    section_title(d, "Mobile PWA Client", pwa, COLORS["green"])
    label(d, (110, 195, 425, 265), "Progressive Web App", COLORS["green"], fnt=F_BOX)
    label(
        d,
        (75, 305, 460, 465),
        "PWA Runtime\nBrowser\nService Worker\nWeb App Manifest\nCache Storage\nInstallable App Shell",
        COLORS["green"],
        fnt=F_TINY,
    )
    label(
        d,
        (75, 505, 460, 735),
        "Mobile Feature Modules\nLogin / Register / Profile\nCommunity Feed / Posts / Comments\nFriends / QR Scan / Friend Game\nDashboard / Stats\nMobile AI Coach Chat\nNotification Settings",
        COLORS["green"],
        fnt=F_TINY,
    )
    label(d, (95, 775, 440, 875), "Mobile API Client\nmobile/src/api.ts\nHTTPS API calls\nStreaming HTTP client", COLORS["blue"], fnt=F_TINY)

    cloudrun = (540, 120, 1015, 925)
    rounded(d, cloudrun, COLORS["orange_fill"], COLORS["orange"], width=3)
    section_title(d, "Cloud Run Mobile-Lite API", cloudrun, COLORS["orange"])
    label(d, (610, 190, 945, 250), "cuevex-mobile-cloud", COLORS["orange"], fnt=F_BOX)
    label(d, (585, 285, 970, 380), "Runtime Status\n/health\n/api/diagnostics/cloud-mobile\ndeploy_mode: cloud_mobile", COLORS["orange"], fnt=F_TINY)
    y = 415
    for text, col in [
        ("Auth + Account API\nlogin / profile / dashboard", COLORS["orange"]),
        ("Community API\nposts / comments / likes / bookmarks", COLORS["orange"]),
        ("Friends / Game API\nQR invite / friend match / start game", COLORS["orange"]),
        ("AI Coach HTTP API\nchat / stream", COLORS["red"]),
        ("Push Token / Notification API\npush token / events / delivery records", COLORS["orange"]),
    ]:
        label(d, (585, y, 970, y + 72), text, col, fnt=F_TINY)
        y += 86

    supabase = (1055, 120, 1460, 925)
    rounded(d, supabase, COLORS["gray_fill"], COLORS["gray"], width=3)
    section_title(d, "Supabase Backend", supabase, COLORS["gray"])
    label(
        d,
        (1100, 270, 1415, 700),
        "Supabase Services\naccount store backend\nprofiles\ncommunity tables\nfriends / game tables\nselected analytics\nnotification records\nRPC functions",
        COLORS["gray"],
        fnt=F_SMALL,
    )

    notify = (1500, 120, 1890, 925)
    rounded(d, notify, COLORS["gray_fill"], COLORS["gray"], width=3)
    d.text((1560, 145), "External Notification\nService", font=font(28, True), fill=COLORS["gray"], align="center")
    label(d, (1550, 300, 1840, 390), "Expo Push API", COLORS["purple"], fnt=F_BOX)
    label(d, (1550, 500, 1840, 590), "push tickets\npush receipts", COLORS["purple"], fnt=F_SMALL)
    label(d, (1550, 700, 1840, 790), "device notification delivery", COLORS["purple"], fnt=F_SMALL)

    coach = (640, 945, 1330, 1035)
    label(d, coach, "Backend AI Coach Bridge -> AI Coach WebSocket Service\n/ws/coach internal backend channel only", COLORS["red"], COLORS["red_fill"], fnt=F_TINY)

    # Client-side flow stays inside PWA, then exits only through Mobile API Client.
    arrow(d, (268, 265), (268, 305), COLORS["green"])
    arrow(d, (268, 465), (268, 505), COLORS["green"])
    arrow(d, (268, 735), (268, 775), COLORS["green"])
    arrow(d, (440, 825), (585, 455), COLORS["blue"])
    arrow(d, (440, 825), (585, 713), COLORS["red"], dashed=True)

    # Backend-only integrations.
    arrow(d, (970, 520), (1100, 410), COLORS["gray"])
    arrow(d, (970, 606), (1100, 470), COLORS["gray"])
    arrow(d, (970, 692), (1100, 535), COLORS["gray"])
    arrow(d, (970, 799), (1100, 610), COLORS["purple"], dashed=True)
    poly_arrow(d, [(970, 778), (1028, 778), (1028, 96), (1482, 96), (1550, 345)], COLORS["gray"])
    arrow(d, (1695, 390), (1695, 500), COLORS["gray"])
    arrow(d, (1695, 590), (1695, 700), COLORS["gray"])
    poly_arrow(d, [(970, 713), (985, 713), (985, 990), (640, 990)], COLORS["red"])

    legend(
        d,
        1465,
        805,
        [
            (COLORS["blue"], "HTTPS REST API"),
            (COLORS["red"], "AI Coach HTTP stream"),
            (COLORS["purple"], "selected analytics / sync"),
            (COLORS["gray"], "external cloud service call"),
        ],
    )
    save(img, "04_pwa_cloud_mobile_api_architecture.png")
    save(img, "04_mobile_architecture.png")


def ai_coach() -> None:
    img, d = canvas("AI Coach Integration — Correct Service Boundaries", COLORS["red"])
    clients = (35, 390, 300, 755)
    rounded(d, clients, COLORS["blue_fill"], COLORS["blue"], width=3)
    section_title(d, "Clients", clients, COLORS["blue"])
    label(d, (70, 505, 265, 670), "Frontend Web\nMobile\nHTTP chat\nStreaming", COLORS["blue"], fnt=F_SMALL)

    backend = (350, 145, 870, 980)
    rounded(d, backend, COLORS["orange_fill"], COLORS["orange"], width=3)
    section_title(d, "Backend Core Hub", backend, COLORS["orange"])
    y = 230
    for text in [
        "AI Coach HTTP Endpoints\n/api/coach/chat\n/api/coach/chat/stream",
        "Context Router\nanalytics intent\nlive table intent\npractice intent",
        "Runtime + Analytics Context\nlatest_analysis_data\nmulti_plan\nshot_events\nplayer stats",
        "CoachPayloadBuilder\ncoach.analytics_context.v1\nplanner context",
        "CoachBridge\ninternal WebSocket client",
    ]:
        label(d, (405, y, 820, y + 115), text, COLORS["orange"], fnt=F_TINY)
        y += 140

    service = (930, 95, 1625, 1000)
    rounded(d, service, COLORS["red_fill"], COLORS["red"], width=4)
    section_title(d, "AI Coach WebSocket Service", service, COLORS["red"])
    y = 185
    for text in [
        "WebSocket /ws/coach\ninternal backend channel only",
        "ConversationRouter\nchat / suggest / analytics advice",
        "Context Consumption\nsemantic / planner / analytics / conversation",
        "Prompt Builder",
        "OpenAI-compatible LLM API\nvLLM / Gemma",
        "Streaming Coach Response\ncoach.delta / coach.replace / coach.result / coach.error",
    ]:
        label(d, (985, y, 1570, y + 100), text, COLORS["red"], fnt=F_SMALL if "Prompt" not in text else F_BOX)
        y += 128

    ext = (1660, 365, 1905, 730)
    rounded(d, ext, COLORS["blue_fill"], COLORS["cyan"], width=3)
    d.text((1680, 390), "External Inference", font=font(26, True), fill=COLORS["cyan"])
    label(d, (1725, 485, 1865, 630), "Gemma\nvLLM Service\nHTTP API", COLORS["cyan"], fnt=F_SMALL)

    arrow(d, (300, 580), (405, 290), COLORS["blue"])
    for y1, y2 in [(345, 370), (485, 510), (625, 650), (765, 790)]:
        arrow(d, (612, y1), (612, y2), COLORS["orange"])
    arrow(d, (820, 850), (985, 235), COLORS["red"])
    arrow(d, (1277, 285), (1277, 313), COLORS["red"])
    arrow(d, (1277, 413), (1277, 441), COLORS["red"])
    arrow(d, (1277, 541), (1277, 569), COLORS["red"])
    arrow(d, (1277, 669), (1277, 697), COLORS["red"])
    arrow(d, (1570, 750), (1725, 555), COLORS["cyan"])
    arrow(d, (1725, 610), (1570, 900), COLORS["cyan"])
    arrow(d, (985, 890), (820, 850), COLORS["red"])
    save(img, "05_ai_coach_service_boundaries.png")


def main() -> None:
    backend_flow()
    frontend_web()
    replay_stats()
    mobile_architecture()
    ai_coach()
    print(f"Generated architecture images in {OUT_DIR}")


if __name__ == "__main__":
    main()
