const C = {
  bg: "#F6F1E7",
  ink: "#15201D",
  muted: "#5E6A64",
  deep: "#12342F",
  teal: "#1D6F64",
  gold: "#D9A441",
  clay: "#C0643D",
  blue: "#315B8C",
  panel: "#FFFDF7",
  line: "#D9D1C2",
};

const tocItems = [
  "研究背景與動機",
  "問題定義",
  "系統目標",
  "系統架構",
  "使用技術",
  "核心功能",
  "系統畫面展示",
  "分析流程",
  "實作成果",
  "遇到問題與解決方式",
  "結論與未來展望",
];

export const slides = [
  {
    type: "cover",
    kicker: "專題報告｜8 分鐘",
    title: "CueVex 智慧撞球訓練平台",
    subtitle: "即時球位辨識、投影輔助、AI Coach 與 Mobile 數據服務整合",
    claim: "把撞球練習從一次性觀看，改成可辨識、可建議、可回放、可追蹤的訓練閉環。",
  },
  {
    type: "toc",
    kicker: "目錄",
    title: "報告大綱",
    claim: "本報告依照背景、問題、目標、架構、技術、功能、畫面、流程、成果、問題解法與展望說明 CueVex。",
  },
  {
    kicker: "01 研究背景與動機",
    title: "撞球訓練需要即時、客觀、可累積的回饋",
    claim: "傳統練習多依賴教練經驗或事後觀看影片，缺少能立即量化球位、路線與練習成效的工具。",
    blocks: [
      ["現場需求", "玩家需要在擊球前後快速知道球路選擇、母球控制與進攻風險。"],
      ["技術機會", "Computer Vision、WebSocket、LLM 與雲端資料庫已足以串起即時訓練流程。"],
      ["專題動機", "將辨識、投影、AI 建議與手機數據整合，建立可持續進步的訓練平台。"],
    ],
  },
  {
    kicker: "02 問題定義",
    title: "目前練習流程的資料斷點太多",
    claim: "單純偵測球不等於完成訓練系統；真正問題是即時畫面、擊球結果、回放與長期紀錄沒有被串起來。",
    blocks: [
      ["即時回饋不足", "玩家打完一桿後，很難立刻知道路線是否合理、力道是否過大或母球停位是否穩定。"],
      ["紀錄難以追蹤", "對戰、練習、回放與能力變化若沒有統一資料模型，後續分析會失去依據。"],
      ["跨裝置困難", "桌面端有相機與投影硬體，手機端需要帳號、社群與數據服務，兩者邊界必須清楚。"],
    ],
  },
  {
    kicker: "03 系統目標",
    title: "建立從現場判斷到手機追蹤的完整閉環",
    claim: "CueVex 不是單一模型展示，而是一套能看、能練、能問、能回放、能追蹤的產品型系統。",
    metrics: [
      ["即時辨識", "偵測球位、球色、球號與穩定狀態，支援畫面 overlay。"],
      ["訓練輔助", "用校正與投影顯示擺球位置、目標袋口、輔助線與母球停點。"],
      ["AI Coach", "把盤面語意轉成自然語氣建議，降低玩家理解門檻。"],
      ["Mobile 數據", "提供登入、社群、個人頁、封鎖安全與能力總覽。"],
    ],
  },
  {
    kicker: "04 系統架構",
    title: "桌面端處理低延遲硬體，雲端承接手機資料服務",
    claim: "相機、YOLO、投影、錄影與 MJPEG 留在本機；Cloud Run mobile-lite 專注手機 API，Supabase 管理帳號與社群資料。",
    flow: [
      ["桌面前端", "React / TypeScript 操作介面"],
      ["桌面後端", "FastAPI / MJPEG / WebSocket"],
      ["AI Coach", "8010 WebSocket / vLLM Gemma"],
      ["Mobile 雲端", "Expo / Cloud Run / Supabase"],
    ],
  },
  {
    kicker: "05 使用技術",
    title: "以可部署的工程技術串接 AI、前端、後端與雲端",
    claim: "每項技術都對應到實際系統責任，避免只堆疊工具名詞。",
    tech: [
      ["AI 視覺", "YOLO、OpenCV、球色/球號後處理、穩定性偵測"],
      ["後端", "Python、FastAPI、REST API、WebSocket、SQLite"],
      ["前端", "React、TypeScript、Vite、Burn-in MJPEG 播放"],
      ["AI Coach", "vLLM、Gemma、語意摘要、對話記憶"],
      ["Mobile", "Expo、React Native、Cloud Run mobile-lite"],
      ["資料庫", "Supabase、帳號 Session、社群貼文與好友資料"],
    ],
  },
  {
    kicker: "06 核心功能",
    title: "功能設計圍繞訓練閉環，而不是單點展示",
    claim: "核心功能分成現場輔助、AI 建議、回放分析與手機追蹤四個面向。",
    metrics: [
      ["現場監控", "即時串流、球框 overlay、系統狀態、連線健康。"],
      ["練習投影", "球桌校正、擺球輔助、路線提示、準度訓練。"],
      ["AI 對話", "畫面分析、產生建議、非畫面問答、操作導覽。"],
      ["回放與 Mobile", "錄影列表、事件紀錄、個人頁、社群、數據總覽。"],
    ],
  },
  {
    type: "screens",
    kicker: "07 系統畫面展示",
    title: "桌面端、AI Coach 與 Mobile 形成三個主要使用入口",
    claim: "使用者在桌面端完成即時訓練，在 AI Coach 取得建議，並於手機端追蹤個人資料與數據。",
    screens: [
      ["桌面監控", "Burn-in 串流、YOLO 狀態、練習/路線面板"],
      ["AI Coach", "畫面分析、產生建議、自然語氣問答"],
      ["Mobile App", "登入、社群、個人頁、能力總覽"],
    ],
  },
  {
    kicker: "08 分析流程",
    title: "從影像到建議，先產生可信 metadata 再交給 AI",
    claim: "分析流程先完成球桌校正與偵測，再將盤面轉成語意摘要，避免模型直接讀取混亂的原始狀態。",
    flow: [
      ["影像輸入", "相機畫面 / ROI"],
      ["辨識與校正", "YOLO / 球桌座標 / 球色球號"],
      ["語意摘要", "合法目標 / 袋口線索 / 風險"],
      ["輸出回饋", "Overlay / 投影 / AI 建議 / 回放"],
    ],
  },
  {
    kicker: "09 實作成果",
    title: "目前已完成可示範的端到端系統",
    claim: "成果橫跨桌面端、AI Coach、遠端存取與 Mobile V1，具備完整專題展示素材。",
    matrix: [
      ["桌面端", "FastAPI + React", "監控、YOLO、投影校正、練習、錄影回放"],
      ["AI Coach", "vLLM + Gemma", "對話記憶、畫面分析、產生建議"],
      ["Mobile", "Expo + Cloud Run", "登入、社群、個人頁、封鎖安全、數據看板"],
      ["工程化", "Docs + diagnostics", "API 文件、診斷端點、測試規範、部署腳本"],
    ],
  },
  {
    kicker: "10 遇到問題與解決方式",
    title: "主要挑戰集中在即時同步、部署邊界與錯誤診斷",
    claim: "專題不只完成功能，也把常見錯誤轉成可診斷、可維護的工程流程。",
    problems: [
      ["畫面與 overlay 同步", "改採後端 Burn-in MJPEG，前端播放已合成畫面，降低疊圖延遲與座標偏移。"],
      ["Mobile 500 難定位", "新增 Cloud Run 與 profile diagnostics，回傳 Supabase 連線與資料表狀態。"],
      ["AI Coach 服務漂移", "固定 8010 WebSocket service，啟動時檢查 vLLM ready 與 health 狀態。"],
      ["功能使用邊界", "遊玩模式限制 AI Coach，避免即時戰術建議造成作弊疑慮。"],
    ],
  },
  {
    kicker: "11 結論與未來展望",
    title: "CueVex 已形成可持續迭代的智慧訓練平台",
    claim: "下一階段重點是提高數據可信度，讓 AI Coach 從建議工具進一步成為個人化訓練系統。",
    blocks: [
      ["結論", "CueVex 將即時辨識、投影練習、AI 建議、回放與手機數據整合成完整訓練閉環。"],
      ["近期改進", "補齊單球擊球事件、角度誤差、力道誤差與母球落點紀錄，提高分析粒度。"],
      ["未來展望", "支援更精準的能力評分、個人化訓練排程、多桌管理與更穩定的正式部署。"],
    ],
  },
];

function bg(slide, ctx) {
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 720, fill: C.bg });
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 72, fill: C.deep });
  ctx.addShape(slide, { x: 0, y: 680, w: 1280, h: 40, fill: "#E9DFC9" });
}

function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: value,
    x,
    y,
    w,
    h,
    fontSize: opts.size ?? 24,
    color: opts.color ?? C.ink,
    bold: opts.bold ?? false,
    typeface: opts.face ?? (opts.title ? "Aptos Display" : "Aptos"),
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line("#00000000", 0),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
  });
}

function header(slide, ctx, data, index) {
  text(slide, ctx, data.kicker, 54, 22, 720, 32, { size: 18, color: "#E9DFC9", bold: true });
  text(slide, ctx, `${index + 1} / ${slides.length}`, 1110, 21, 110, 32, { size: 18, color: "#E9DFC9", align: "right" });
}

function footer(slide, ctx) {
  text(slide, ctx, "CueVex｜智慧撞球訓練平台", 54, 686, 400, 20, { size: 13, color: C.muted });
}

function titleBlock(slide, ctx, data) {
  text(slide, ctx, data.title, 54, 104, 820, 92, { size: 38, bold: true, title: true, color: C.deep });
  text(slide, ctx, data.claim, 58, 205, 880, 58, { size: 21, color: C.muted });
}

function panel(slide, ctx, x, y, w, h, fill = C.panel) {
  ctx.addShape(slide, { x, y, w, h, fill, line: ctx.line(C.line, 1) });
}

function renderCover(slide, ctx, data) {
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 720, fill: C.deep });
  ctx.addShape(slide, { x: 800, y: 0, w: 480, h: 720, fill: C.teal });
  ctx.addShape(slide, { x: 865, y: 90, w: 300, h: 300, fill: "#0C221F", line: ctx.line(C.gold, 3) });
  ctx.addShape(slide, { geometry: "ellipse", x: 930, y: 150, w: 50, h: 50, fill: "#F6F1E7", line: ctx.line("#F6F1E7", 1) });
  ctx.addShape(slide, { geometry: "ellipse", x: 1028, y: 240, w: 42, h: 42, fill: C.gold, line: ctx.line(C.gold, 1) });
  ctx.addShape(slide, { geometry: "ellipse", x: 955, y: 310, w: 46, h: 46, fill: C.clay, line: ctx.line(C.clay, 1) });
  ctx.addShape(slide, { x: 908, y: 360, w: 220, h: 5, fill: "#F6F1E7" });
  text(slide, ctx, data.kicker, 72, 78, 520, 34, { size: 19, color: C.gold, bold: true });
  text(slide, ctx, data.title, 72, 150, 690, 120, { size: 48, color: "#FFFDF7", bold: true, title: true });
  text(slide, ctx, data.subtitle, 76, 292, 660, 58, { size: 25, color: "#DCEAE3" });
  text(slide, ctx, data.claim, 76, 456, 660, 86, { size: 24, color: "#FFFDF7" });
  text(slide, ctx, "組員 / 指導老師 / 課程名稱：可於此頁直接編輯", 76, 626, 700, 30, { size: 17, color: "#BFD4CE" });
  text(slide, ctx, `1 / ${slides.length}`, 1138, 650, 86, 28, { size: 17, color: "#DCEAE3", align: "right" });
}

function renderToc(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  const left = 92;
  const top = 296;
  tocItems.forEach((item, i) => {
    const col = i < 6 ? 0 : 1;
    const row = col === 0 ? i : i - 6;
    const x = left + col * 560;
    const y = top + row * 52;
    text(slide, ctx, String(i + 1).padStart(2, "0"), x, y, 50, 28, { size: 19, color: C.gold, bold: true });
    text(slide, ctx, item, x + 58, y, 300, 28, { size: 22, color: C.deep, bold: i === 0 });
    text(slide, ctx, String(i + 3), x + 430, y, 38, 28, { size: 18, color: C.muted, align: "right" });
  });
}

function renderBlocks(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  const y0 = 306;
  data.blocks.forEach((b, i) => {
    const x = 70 + i * 390;
    panel(slide, ctx, x, y0, 340, 245);
    ctx.addShape(slide, { x, y: y0, w: 340, h: 10, fill: [C.teal, C.gold, C.clay][i % 3] });
    text(slide, ctx, b[0], x + 24, y0 + 34, 292, 34, { size: 24, bold: true, color: C.deep });
    text(slide, ctx, b[1], x + 24, y0 + 88, 292, 126, { size: 19, color: C.muted });
  });
}

function renderFlow(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  const x0 = 64;
  const y = 326;
  data.flow.forEach((b, i) => {
    const x = x0 + i * 300;
    panel(slide, ctx, x, y, 236, 164, i % 2 ? "#FFFDF7" : "#FDF7EA");
    ctx.addShape(slide, { x: x + 20, y: y + 22, w: 48, h: 48, fill: [C.teal, C.blue, C.gold, C.clay][i] });
    text(slide, ctx, b[0], x + 20, y + 84, 196, 30, { size: 23, bold: true, color: C.deep });
    text(slide, ctx, b[1], x + 20, y + 116, 196, 34, { size: 15, color: C.muted });
    if (i < data.flow.length - 1) {
      ctx.addShape(slide, { x: x + 248, y: y + 78, w: 34, h: 6, fill: C.teal });
      ctx.addShape(slide, { x: x + 274, y: y + 70, w: 14, h: 22, fill: C.teal });
    }
  });
}

function renderMetrics(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  data.metrics.forEach((m, i) => {
    const x = 72 + (i % 2) * 570;
    const y = 302 + Math.floor(i / 2) * 145;
    panel(slide, ctx, x, y, 500, 108);
    ctx.addShape(slide, { x, y, w: 12, h: 108, fill: [C.teal, C.gold, C.clay, C.blue][i] });
    text(slide, ctx, m[0], x + 32, y + 22, 150, 28, { size: 22, bold: true, color: C.deep });
    text(slide, ctx, m[1], x + 190, y + 18, 270, 62, { size: 17, color: C.muted });
  });
}

function renderTech(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  data.tech.forEach((m, i) => {
    const x = 70 + (i % 3) * 390;
    const y = 292 + Math.floor(i / 3) * 142;
    panel(slide, ctx, x, y, 340, 108);
    ctx.addShape(slide, { x, y, w: 340, h: 8, fill: [C.teal, C.gold, C.clay, C.blue, C.teal, C.gold][i] });
    text(slide, ctx, m[0], x + 22, y + 25, 290, 26, { size: 21, bold: true, color: C.deep });
    text(slide, ctx, m[1], x + 22, y + 58, 292, 38, { size: 16, color: C.muted });
  });
}

function renderMatrix(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  const x = 72, y = 300, w = 1136, rowH = 72;
  panel(slide, ctx, x, y, w, rowH * 4 + 44);
  text(slide, ctx, "模組", x + 28, y + 16, 190, 28, { size: 18, bold: true, color: C.teal });
  text(slide, ctx, "技術", x + 320, y + 16, 330, 28, { size: 18, bold: true, color: C.teal });
  text(slide, ctx, "成果", x + 760, y + 16, 310, 28, { size: 18, bold: true, color: C.teal });
  data.matrix.forEach((r, i) => {
    const yy = y + 52 + i * rowH;
    ctx.addShape(slide, { x: x + 18, y: yy, w: w - 36, h: 1, fill: C.line });
    text(slide, ctx, r[0], x + 28, yy + 18, 210, 28, { size: 21, bold: true, color: C.deep });
    text(slide, ctx, r[1], x + 320, yy + 18, 330, 28, { size: 19, color: C.muted });
    text(slide, ctx, r[2], x + 760, yy + 18, 330, 28, { size: 18, color: C.muted });
  });
}

function renderScreens(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  data.screens.forEach((s, i) => {
    const x = 72 + i * 390;
    const y = 292;
    panel(slide, ctx, x, y, 340, 250, "#FFFDF7");
    ctx.addShape(slide, { x: x + 18, y: y + 20, w: 304, h: 148, fill: i === 0 ? "#0C221F" : i === 1 ? "#FDF7EA" : "#EAF2EF", line: ctx.line(C.line, 1) });
    if (i === 0) {
      ctx.addShape(slide, { geometry: "ellipse", x: x + 82, y: y + 64, w: 22, h: 22, fill: "#F6F1E7" });
      ctx.addShape(slide, { geometry: "ellipse", x: x + 188, y: y + 92, w: 20, h: 20, fill: C.gold });
      ctx.addShape(slide, { x: x + 56, y: y + 136, w: 220, h: 4, fill: "#F6F1E7" });
    } else if (i === 1) {
      ctx.addShape(slide, { x: x + 42, y: y + 48, w: 220, h: 24, fill: C.deep });
      ctx.addShape(slide, { x: x + 42, y: y + 88, w: 178, h: 18, fill: C.teal });
      ctx.addShape(slide, { x: x + 42, y: y + 120, w: 238, h: 18, fill: C.gold });
    } else {
      ctx.addShape(slide, { geometry: "ellipse", x: x + 42, y: y + 44, w: 46, h: 46, fill: C.teal });
      ctx.addShape(slide, { x: x + 110, y: y + 50, w: 150, h: 14, fill: C.deep });
      ctx.addShape(slide, { x: x + 42, y: y + 120, w: 238, h: 16, fill: C.gold });
      ctx.addShape(slide, { x: x + 42, y: y + 146, w: 198, h: 16, fill: C.clay });
    }
    text(slide, ctx, s[0], x + 22, y + 184, 290, 26, { size: 22, bold: true, color: C.deep });
    text(slide, ctx, s[1], x + 22, y + 215, 292, 24, { size: 16, color: C.muted });
  });
}

function renderProblems(slide, ctx, data) {
  titleBlock(slide, ctx, data);
  data.problems.forEach((p, i) => {
    const x = 72 + (i % 2) * 570;
    const y = 292 + Math.floor(i / 2) * 150;
    panel(slide, ctx, x, y, 500, 118);
    ctx.addShape(slide, { x, y, w: 12, h: 118, fill: [C.teal, C.gold, C.clay, C.blue][i] });
    text(slide, ctx, p[0], x + 32, y + 22, 410, 28, { size: 21, bold: true, color: C.deep });
    text(slide, ctx, p[1], x + 32, y + 58, 420, 40, { size: 16, color: C.muted });
  });
}

export async function renderSlide(presentation, ctx, index) {
  const slide = presentation.slides.add();
  const data = slides[index];
  if (!data) throw new Error(`Unknown slide index ${index}`);
  if (data.type === "cover") {
    renderCover(slide, ctx, data);
    return slide;
  }
  bg(slide, ctx);
  header(slide, ctx, data, index);
  if (data.type === "toc") renderToc(slide, ctx, data);
  else if (data.type === "screens") renderScreens(slide, ctx, data);
  else if (data.flow) renderFlow(slide, ctx, data);
  else if (data.tech) renderTech(slide, ctx, data);
  else if (data.matrix) renderMatrix(slide, ctx, data);
  else if (data.metrics) renderMetrics(slide, ctx, data);
  else if (data.problems) renderProblems(slide, ctx, data);
  else renderBlocks(slide, ctx, data);
  footer(slide, ctx);
  return slide;
}
