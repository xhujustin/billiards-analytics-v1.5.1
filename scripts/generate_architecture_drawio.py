from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture" / "CueVex-updated-architecture-20260624.drawio"


COLORS = {
    "orange": ("#F9E4D3", "#F58A1F"),
    "blue": ("#DDF1FA", "#0C78CF"),
    "green": ("#DDF3E9", "#08A86B"),
    "purple": ("#F0D9F7", "#7A36C3"),
    "red": ("#F8C9CF", "#EF1E2D"),
    "gray": ("#F0F0F0", "#646464"),
    "white": ("#FFFFFF", "#111111"),
}


class Page:
    def __init__(self, name: str):
        self.name = name
        self.cells: list[str] = [
            '<mxCell id="0"/>',
            '<mxCell id="1" parent="0"/>',
        ]
        self.n = 2

    def _id(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}_{self.n}"

    def rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: str,
        color: str,
        *,
        font_size: int = 16,
        bold: bool = False,
        radius: bool = True,
    ) -> str:
        cid = self._id("v")
        fill, stroke = COLORS[color]
        style = (
            f"rounded={1 if radius else 0};whiteSpace=wrap;html=1;"
            f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
            f"fontSize={font_size};fontColor=#111111;"
            f"fontStyle={1 if bold else 0};align=center;verticalAlign=middle;"
        )
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(text)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            "</mxCell>"
        )
        return cid

    def group_box(self, x: int, y: int, w: int, h: int, title: str, color: str) -> str:
        cid = self._id("g")
        fill, stroke = COLORS[color]
        style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
            "strokeWidth=3;fontSize=24;fontStyle=1;fontColor="
            f"{stroke};align=center;verticalAlign=top;spacingTop=18;"
        )
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(title)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            "</mxCell>"
        )
        return cid

    def title(self, text: str, color: str = "orange") -> None:
        _, stroke = COLORS[color]
        self.cells.append(
            f'<mxCell id="{self._id("t")}" value="{escape(text)}" '
            f'style="text;html=1;strokeColor=none;fillColor=none;align=center;'
            f'verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=34;'
            f'fontStyle=1;fontColor={stroke};" vertex="1" parent="1">'
            '<mxGeometry x="160" y="20" width="1600" height="60" as="geometry"/>'
            "</mxCell>"
        )

    def edge(self, source: str, target: str, color: str = "orange", dashed: bool = False, label: str = "") -> str:
        cid = self._id("e")
        _, stroke = COLORS[color]
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
            f"html=1;strokeColor={stroke};strokeWidth=3;endArrow=block;endFill=1;"
            f"dashed={1 if dashed else 0};"
        )
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{source}" target="{target}"><mxGeometry relative="1" as="geometry"/></mxCell>'
        )
        return cid

    def xml(self) -> str:
        body = "\n".join(self.cells)
        return (
            f'<diagram name="{escape(self.name)}">'
            '<mxGraphModel dx="1920" dy="1080" grid="1" gridSize="10" guides="1" tooltips="1" '
            'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1920" '
            'pageHeight="1080" math="0" shadow="0"><root>'
            f"{body}"
            "</root></mxGraphModel></diagram>"
        )


def backend_page() -> Page:
    p = Page("01 Backend Architecture Flow")
    p.title("CueVex Backend Architecture Flow - Desktop FastAPI Runtime", "orange")
    p.group_box(220, 110, 1480, 880, "Backend Core Runtime", "orange")
    frontend = p.rect(30, 230, 180, 190, "Frontend Web\nREST API\nWebSocket Metadata\nMJPEG Stream", "blue")
    coach_ext = p.rect(1740, 230, 160, 150, "AI Coach Service\n/ws/coach\ninternal channel", "red")
    mobile_ext = p.rect(1740, 470, 160, 170, "Mobile / Cloud API\nAuth\nCommunity\nDashboard\nPush", "green")
    cloud_ext = p.rect(1740, 760, 160, 150, "Cloud Services\nSupabase selected data\nExpo Push", "gray")

    input_layer = p.rect(280, 190, 250, 170, "Input Layer\nCamera / Video Source\nOpenCV Capture\nImage Processor", "orange")
    vision = p.rect(610, 190, 300, 170, "Vision Runtime\nPoolTracker\nYOLO Detection\nTable ROI\nBall Color / Number", "orange")
    weights = p.rect(950, 165, 260, 80, "YOLO Weights\nmodel input", "orange")
    state = p.rect(970, 300, 320, 160, "Runtime State Hub\nlatest_analysis_data\nRuntime Packet\nmetadata packet\nmulti_plan / planner_error", "orange")
    fastapi = p.rect(1360, 220, 260, 210, "FastAPI Service Layer\nREST API Routers\nWebSocket Metadata\nMJPEG Endpoints\nControl APIs", "orange")
    game = p.rect(280, 520, 270, 180, "Game / Practice Layer\nGameManager\nPractice Mode\nRule / Target State\nShot Event Detection", "orange")
    planner = p.rect(650, 520, 280, 200, "Planning / AR / Calibration\nRoute Planner\nCalibration / ArUco\nProjector Renderer\nAR Metadata", "orange")
    replay = p.rect(1000, 540, 280, 200, "Replay / Stats Layer\nRecordingManager\nLocal Artifacts\nSQLite recordings.db\nAnalytics Aggregation", "purple")
    bridge = p.rect(1340, 560, 300, 210, "AI Coach Bridge Layer\nContext Router\nCoachPayloadBuilder\nCoachBridge\n/api/coach/chat/stream", "red")

    for a, b, c in [
        (input_layer, vision, "orange"),
        (weights, vision, "orange"),
        (vision, state, "orange"),
        (state, fastapi, "orange"),
        (state, planner, "orange"),
        (state, replay, "purple"),
        (game, replay, "purple"),
        (planner, replay, "purple"),
        (replay, bridge, "red"),
        (fastapi, frontend, "blue"),
        (fastapi, mobile_ext, "green"),
        (bridge, coach_ext, "red"),
        (replay, cloud_ext, "gray"),
    ]:
        p.edge(a, b, c, dashed=(c == "gray"))
    return p


def frontend_page() -> Page:
    p = Page("02 Frontend Web Architecture")
    p.title("Frontend Web Architecture - Editable Components", "blue")
    p.group_box(40, 115, 1500, 860, "Frontend Web Architecture", "blue")
    app = p.rect(620, 180, 450, 75, "Dashboard.tsx / React + Vite App Shell", "blue", bold=True)
    ui_box = p.group_box(85, 300, 390, 580, "UI Pages", "blue")
    access_box = p.group_box(520, 300, 920, 580, "Client Access Layer", "blue")
    backend = p.group_box(1600, 190, 280, 730, "Backend APIs", "orange")
    runtime = p.rect(590, 395, 780, 90, "Frontend Runtime Client", "blue", bold=True)

    ui_items = [
        p.rect(125, 380 + i * 75, 300, 55, text, "red" if "Coach" in text else ("purple" if "Replay" in text else "blue"), font_size=15)
        for i, text in enumerate(
            [
                "Auth / Guest Gate",
                "Live Stream / Monitor",
                "Game / Practice",
                "Replay / Stats",
                "Settings / Camera / Calibration",
                "AI Coach Chat",
            ]
        )
    ]
    clients = [
        p.rect(590 + i * 155, 535, 145, 110, text, "blue", font_size=14)
        for i, text in enumerate(["Session / Auth Client", "REST API Client", "WebSocket Control Client", "Metadata Buffer", "Connection Health"])
    ]
    mjpeg = p.rect(590, 715, 360, 110, "MJPEG Stream Viewer\n/stream/monitor\n/stream/projector", "orange", font_size=15)
    coach = p.rect(1010, 715, 360, 110, "AI Coach HTTP Stream Client\nPOST /api/coach/chat/stream", "red", font_size=15)
    backend_items = [
        p.rect(1640, 300 + i * 90, 205, 65, text, "red" if "Coach" in text else ("purple" if "Replay" in text else ("blue" if "WebSocket" in text else "orange")), font_size=14)
        for i, text in enumerate(
            [
                "Auth / Session API",
                "WebSocket / Metadata API",
                "MJPEG Stream API",
                "Replay / Stats REST API",
                "Camera / Calibration REST API",
                "AI Coach HTTP Bridge",
            ]
        )
    ]
    p.edge(app, runtime, "blue")
    for item in ui_items:
        p.edge(item, runtime, "blue")
    for item in clients:
        p.edge(runtime, item, "blue")
    p.edge(runtime, mjpeg, "orange")
    p.edge(runtime, coach, "red")
    p.edge(runtime, backend_items[1], "blue")
    p.edge(mjpeg, backend_items[2], "orange")
    p.edge(ui_items[3], backend_items[3], "purple")
    p.edge(coach, backend_items[5], "red")
    return p


def replay_page() -> Page:
    p = Page("03 Replay Stats Backend Subsystem")
    p.title("Replay / Stats - Backend Subsystem", "purple")
    runtime = p.group_box(40, 250, 280, 660, "Backend Runtime", "orange")
    inputs = p.rect(85, 370, 190, 160, "Runtime Recording Inputs\nFrame snapshots\nShot events\nGame / practice metadata\nPlanner metadata", "orange", font_size=14)
    clients = p.rect(85, 690, 190, 110, "Clients\nFrontend Web\nMobile", "blue", font_size=16)
    p.group_box(360, 130, 1240, 850, "Replay / Stats Subsystem - inside Backend Core Runtime", "purple")
    rec = p.rect(420, 250, 355, 215, "RecordingManager\ncreates recording session\nand writes artifacts", "purple", bold=True)
    files = p.rect(825, 250, 365, 215, "Local Recording Files\nvideo.mp4\nthumbnail.jpg\nmetadata.json\nevents.json", "purple")
    db = p.rect(425, 560, 360, 220, "SQLite recordings.db\nrecordings\nshot_events\npractice_stats\nsync queue", "purple")
    agg = p.rect(850, 560, 340, 220, "Stats / Analytics Aggregation\nplayer\npractice\ngame\noffense\ncue control", "purple")
    api = p.rect(1240, 320, 290, 460, "Replay API\nrecordings\nvideo\nthumbnail\nevents\nStats API\nAnalytics API", "purple")
    sync = p.rect(630, 835, 670, 95, "Supabase Sync\nselected analytics + social metadata only\nlocal video remains local", "blue")
    cloud = p.group_box(1660, 330, 240, 460, "Cloud Services", "gray")
    supa = p.rect(1710, 460, 145, 200, "Supabase\nProfiles\nSocial\nSelected analytics\nPush records", "gray", font_size=16)

    for a, b, c, dashed in [
        (inputs, rec, "orange", False),
        (rec, files, "purple", False),
        (rec, db, "green", False),
        (db, agg, "purple", False),
        (agg, api, "purple", False),
        (clients, api, "orange", False),
        (db, sync, "blue", True),
        (sync, supa, "blue", True),
    ]:
        p.edge(a, b, c, dashed=dashed)
    return p


def pwa_page() -> Page:
    p = Page("04 PWA and Cloud Mobile API")
    p.title("CueVex - PWA and Cloud Mobile API Architecture", "green")
    pwa = p.group_box(35, 120, 465, 805, "Mobile PWA Client", "green")
    app = p.rect(110, 195, 315, 70, "Progressive Web App", "green", bold=True)
    runtime = p.rect(75, 305, 385, 160, "PWA Runtime\nBrowser\nService Worker\nWeb App Manifest\nCache Storage\nInstallable App Shell", "green", font_size=15)
    features = p.rect(75, 505, 385, 230, "Mobile Feature Modules\nLogin / Register / Profile\nCommunity Feed / Posts / Comments\nFriends / QR Scan / Friend Game\nDashboard / Stats\nMobile AI Coach Chat\nNotification Settings", "green", font_size=14)
    client = p.rect(95, 775, 345, 100, "Mobile API Client\nmobile/src/api.ts\nHTTPS API calls\nStreaming HTTP client", "blue", font_size=14)

    cloudrun = p.group_box(540, 120, 475, 805, "Cloud Run Mobile-Lite API", "orange")
    service = p.rect(610, 190, 335, 60, "cuevex-mobile-cloud", "orange", bold=True)
    status = p.rect(585, 285, 385, 95, "Runtime Status\n/health\n/api/diagnostics/cloud-mobile\ndeploy_mode: cloud_mobile", "orange", font_size=14)
    apis = [
        p.rect(585, 415 + i * 86, 385, 72, text, "red" if "Coach" in text else "orange", font_size=14)
        for i, text in enumerate(
            [
                "Auth + Account API\nlogin / profile / dashboard",
                "Community API\nposts / comments / likes / bookmarks",
                "Friends / Game API\nQR invite / friend match / start game",
                "AI Coach HTTP API\nchat / stream",
                "Push Token / Notification API\npush token / events / delivery records",
            ]
        )
    ]

    supabase = p.group_box(1055, 120, 405, 805, "Supabase Backend", "gray")
    supa = p.rect(1100, 270, 315, 430, "Supabase Services\naccount store backend\nprofiles\ncommunity tables\nfriends / game tables\nselected analytics\nnotification records\nRPC functions", "gray")
    notify = p.group_box(1500, 120, 390, 805, "External Notification Service", "gray")
    expo = p.rect(1550, 300, 290, 90, "Expo Push API", "purple", bold=True)
    tickets = p.rect(1550, 500, 290, 90, "push tickets\npush receipts", "purple")
    device = p.rect(1550, 700, 290, 90, "device notification delivery", "purple")
    bridge = p.rect(640, 950, 690, 80, "Backend AI Coach Bridge -> AI Coach WebSocket Service\n/ws/coach internal backend channel only", "red", font_size=14)

    for a, b in [(app, runtime), (runtime, features), (features, client)]:
        p.edge(a, b, "green")
    for target in apis:
        p.edge(client, target, "red" if target == apis[3] else "blue", dashed=(target == apis[3]))
    for target in apis[:3]:
        p.edge(target, supa, "gray")
    p.edge(apis[4], supa, "purple", dashed=True)
    p.edge(apis[4], expo, "gray")
    p.edge(expo, tickets, "gray")
    p.edge(tickets, device, "gray")
    p.edge(apis[3], bridge, "red")
    return p


def ai_coach_page() -> Page:
    p = Page("05 AI Coach Service Boundaries")
    p.title("AI Coach Integration - Correct Service Boundaries", "red")
    clients_box = p.group_box(35, 390, 265, 360, "Clients", "blue")
    clients = p.rect(70, 505, 195, 165, "Frontend Web\nMobile\nHTTP chat\nStreaming", "blue")
    backend = p.group_box(350, 145, 520, 835, "Backend Core Hub", "orange")
    bmods = [
        p.rect(405, 230 + i * 140, 415, 115, text, "orange", font_size=14)
        for i, text in enumerate(
            [
                "AI Coach HTTP Endpoints\n/api/coach/chat\n/api/coach/chat/stream",
                "Context Router\nanalytics intent\nlive table intent\npractice intent",
                "Runtime + Analytics Context\nlatest_analysis_data\nmulti_plan\nshot_events\nplayer stats",
                "CoachPayloadBuilder\ncoach.analytics_context.v1\nplanner context",
                "CoachBridge\ninternal WebSocket client",
            ]
        )
    ]
    service = p.group_box(930, 95, 695, 905, "AI Coach WebSocket Service", "red")
    smods = [
        p.rect(985, 185 + i * 128, 585, 100, text, "red", font_size=16 if i != 3 else 20, bold=(i == 3))
        for i, text in enumerate(
            [
                "WebSocket /ws/coach\ninternal backend channel only",
                "ConversationRouter\nchat / suggest / analytics advice",
                "Context Consumption\nsemantic / planner / analytics / conversation",
                "Prompt Builder",
                "OpenAI-compatible LLM API\nvLLM / Gemma",
                "Streaming Coach Response\ncoach.delta / coach.replace / coach.result / coach.error",
            ]
        )
    ]
    ext = p.group_box(1660, 365, 245, 365, "External Inference", "blue")
    inference = p.rect(1725, 485, 140, 145, "Gemma\nvLLM Service\nHTTP API", "blue")
    p.edge(clients, bmods[0], "blue")
    for a, b in zip(bmods, bmods[1:]):
        p.edge(a, b, "orange")
    p.edge(bmods[-1], smods[0], "red")
    for a, b in zip(smods, smods[1:]):
        p.edge(a, b, "red")
    p.edge(smods[4], inference, "blue")
    p.edge(inference, smods[5], "blue")
    p.edge(smods[5], bmods[-1], "red")
    return p


def main() -> None:
    pages = [backend_page(), frontend_page(), replay_page(), pwa_page(), ai_coach_page()]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    xml = (
        '<mxfile host="app.diagrams.net" modified="2026-06-24T00:00:00.000Z" agent="Codex" '
        'version="24.7.8" type="device">'
        + "".join(page.xml() for page in pages)
        + "</mxfile>"
    )
    OUT.write_text(xml, encoding="utf-8")
    print(f"Generated {OUT}")


if __name__ == "__main__":
    main()
