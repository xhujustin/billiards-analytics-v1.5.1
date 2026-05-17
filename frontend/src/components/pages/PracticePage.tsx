import { useState, useEffect, useRef } from 'react';
import type { PointerEvent } from 'react';
import './PracticePage.css';
import { PageType } from '../Sidebar';
import type { Detection, MetadataUpdatePayload, MultiRoutePlan, RouteCandidate } from '../../sdk/types';

type PracticeMode = 'menu' | 'player-setup' | 'single' | 'pattern';
type PracticeHomeTab = 'recommendations' | 'plans' | 'reports' | 'history';
type PracticePattern = 'straight' | 'cut' | 'bank' | 'combo';
type StrokeTip = 'center' | 'top' | 'draw' | 'left' | 'right' | 'top_left' | 'top_right' | 'draw_left' | 'draw_right';
type StrokePower = 'low' | 'medium' | 'medium_high' | 'high';
type PatternBallId = 'cue' | 'object' | 'object2';
type YoloDrawingMode = 'none' | 'tactical' | 'full';
type SvgPoint = [number, number];

interface PracticeYoloBox {
    id: string;
    label: string;
    confidence: number | null;
    number: number | null;
    color: string | null;
    x: number;
    y: number;
    w: number;
    h: number;
}

interface LookaheadNextRouteSummary {
    id?: string;
    route_type?: string;
    target_ball_number?: number | null;
    success_prob?: number | null;
    position_success_prob?: number | null;
    strategy_label?: string | null;
    route_segments?: Array<{
        type?: string;
        points?: number[][];
        color?: string;
    }>;
    cue_landing_point?: number[] | null;
    cue_landing_zone?: {
        center?: number[] | null;
        radius?: number | null;
        label?: string | null;
    } | null;
    cue_target_zone?: {
        center?: number[] | null;
        radius?: number | null;
        label?: string | null;
    } | null;
    stroke_hint?: {
        type?: string | null;
        power?: string | null;
        spin?: string | null;
    } | null;
}

interface StrokeControl {
    tip: StrokeTip;
    power: StrokePower;
    power_percent?: number;
    tip_x?: number;
    tip_y?: number;
}

interface PatternBall {
    id: PatternBallId;
    label: string;
    x: number;
    y: number;
    type: 'cue' | 'object' | 'object2';
    visible: boolean;
    aim?: [number, number]; // 目標落袋位置（object ball 用）
}

interface PatternRouteSegment {
    type: string;
    points: Array<[number, number]>;
}

interface PatternGhostBall {
    x: number;
    y: number;
    r: number;
}

interface PatternLayout {
    balls: PatternBall[];
    route_segments: PatternRouteSegment[];
    cue_landing_point: [number, number];
    ghost_balls: PatternGhostBall[];
    stroke: StrokeControl;
}

interface PatternGuideOptions {
    cue_laser_enabled: boolean;
    ball_guides_enabled: boolean;
}

interface PracticeStats {
    attempts: number;
    successes: number;
    success_rate: number;
}

interface PracticePageProps {
    onNavigate: (page: PageType) => void;
    metadata?: MetadataUpdatePayload | null;
}

const clamp01 = (value: number) => Math.max(0.02, Math.min(0.98, value));
const PLAYFIELD = { left: 0.06, top: 0.12, width: 0.88, height: 0.76 };
const BALL_DIAMETER_REL = 0.026;

const practiceHomeTabs: Array<{ id: PracticeHomeTab; label: string }> = [
    { id: 'recommendations', label: '訓練推薦' },
    { id: 'plans', label: '我的計畫' },
    { id: 'reports', label: '分析報告' },
    { id: 'history', label: '歷史紀錄' }
];

const trainingRecommendations: Array<{
    title: string;
    description: string;
    tags: string[];
    actionLabel: string;
    practiceType: 'single' | 'pattern';
    visual: 'accuracy' | 'position' | 'pattern' | 'free';
}> = [
    {
        title: '準度訓練',
        description: '針對入袋率、瞄準誤差與出桿穩定度進行訓練',
        tags: ['入袋率', '偏差角度', '出桿穩定'],
        actionLabel: '開始訓練',
        practiceType: 'single',
        visual: 'accuracy'
    },
    {
        title: '走位訓練',
        description: '分析母球停點、力度控制與下一桿連接路線',
        tags: ['母球控制', '力道', '路線規劃'],
        actionLabel: '開始訓練',
        practiceType: 'single',
        visual: 'position'
    },
    {
        title: '球型練習',
        description: '針對固定球型做專項練習，例如直線、切球、反彈球',
        tags: ['固定球型', '專項訓練', '成功率追蹤'],
        actionLabel: '選擇球型',
        practiceType: 'pattern',
        visual: 'pattern'
    },
    {
        title: '一般練習',
        description: '自由擺球練習，支援多球路徑規劃與即時修正',
        tags: ['自由練習', '路徑規劃', 'AI 建議'],
        actionLabel: '開始練習',
        practiceType: 'single',
        visual: 'free'
    }
];

const weeklyTrainingStats = [
    { label: '本週訓練時間', value: '7h 48m' },
    { label: '本週完成局數', value: '24 局' },
    { label: '平均入袋率', value: '68%' },
    { label: '最佳連續成功', value: '12 球' },
    { label: 'AI 綜合評分', value: '82' }
];

const strokePowerOrder: StrokePower[] = ['low', 'medium', 'medium_high', 'high'];
const strokePowerPercentFallback: Record<StrokePower, number> = {
    low: 25,
    medium: 50,
    medium_high: 75,
    high: 100
};

const strokeTipOffset: Record<StrokeTip, [number, number]> = {
    center: [0, 0],
    top: [0, -1],
    draw: [0, 1],
    left: [-1, 0],
    right: [1, 0],
    top_left: [-0.72, -0.72],
    top_right: [0.72, -0.72],
    draw_left: [-0.72, 0.72],
    draw_right: [0.72, 0.72]
};

const getPowerFromPercent = (percent: number): StrokePower => {
    if (percent <= 25) return 'low';
    if (percent <= 50) return 'medium';
    if (percent <= 75) return 'medium_high';
    return 'high';
};

const getStrokePowerPercent = (stroke: StrokeControl): number => {
    if (typeof stroke.power_percent === 'number') {
        return Math.max(1, Math.min(100, Math.round(stroke.power_percent)));
    }
    return strokePowerPercentFallback[stroke.power];
};

const planIncludesLookahead = (plan?: MultiRoutePlan | null): boolean => {
    return Boolean(plan?.routes?.some((route) => route.metadata?.lookahead));
};

const sameRouteIntent = (a?: RouteCandidate | null, b?: RouteCandidate | null): boolean => {
    if (!a || !b) return false;
    return a.route_type === b.route_type
        && a.target_ball_number === b.target_ball_number
        && a.metadata?.combo_second_ball_number === b.metadata?.combo_second_ball_number
        && a.first_contact_ball_number === b.first_contact_ball_number;
};

const promotePlanRoute = (
    plan: MultiRoutePlan,
    routeId: string,
    fallbackRoute?: RouteCandidate | null
): MultiRoutePlan => {
    const selectedRoute = plan.routes?.find((route) => route.id === routeId)
        || plan.routes?.find((route) => sameRouteIntent(route, fallbackRoute));
    if (!selectedRoute) return plan;
    return {
        ...plan,
        best_route: selectedRoute,
        selected_route_id: selectedRoute.id
    } as MultiRoutePlan;
};

const routeTypeLabel = (routeType?: string | null): string => {
    const labels: Record<string, string> = {
        straight: '直接進攻',
        cut: '切球進攻',
        bank: '翻袋進攻',
        combo: '組合進攻',
        kick: '顆星進攻',
        safe_escape: '安全解球',
        contact_only: '合法碰球'
    };
    return routeType ? labels[routeType] || routeType : '-';
};

const getLegacyTipFromOffset = (x: number, y: number): StrokeTip => {
    const deadZone = 0.22;
    const horizontal = Math.abs(x) < deadZone ? '' : x < 0 ? 'left' : 'right';
    const vertical = Math.abs(y) < deadZone ? '' : y < 0 ? 'top' : 'draw';
    if (vertical && horizontal) return `${vertical}_${horizontal}` as StrokeTip;
    if (vertical) return vertical as StrokeTip;
    if (horizontal) return horizontal as StrokeTip;
    return 'center';
};

const getStrokeTipOffset = (stroke: StrokeControl): [number, number] => {
    if (typeof stroke.tip_x === 'number' && typeof stroke.tip_y === 'number') {
        return [
            Math.max(-1, Math.min(1, stroke.tip_x)),
            Math.max(-1, Math.min(1, stroke.tip_y))
        ];
    }
    return strokeTipOffset[stroke.tip] ?? [0, 0];
};

const getTipDotStyle = (stroke: StrokeControl) => {
    const [x, y] = getStrokeTipOffset(stroke);
    return {
        left: `${50 + x * 42}%`,
        top: `${50 + y * 42}%`
    };
};

const getPatternBalls = (practicePattern: PracticePattern): PatternBall[] => {
    const presets: Record<PracticePattern, PatternBall[]> = {
        straight: [
            { id: 'cue', label: '母球', x: 0.28, y: 0.5, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.56, y: 0.5, type: 'object', visible: true, aim: [0.94, 0.5] },
            { id: 'object2', label: '第二子球', x: 0.7, y: 0.5, type: 'object2', visible: false, aim: [0.94, 0.5] }
        ],
        cut: [
            { id: 'cue', label: '母球', x: 0.28, y: 0.64, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.56, y: 0.42, type: 'object', visible: true, aim: [0.94, 0.12] },
            { id: 'object2', label: '第二子球', x: 0.72, y: 0.42, type: 'object2', visible: false, aim: [0.94, 0.12] }
        ],
        bank: [
            { id: 'cue', label: '母球', x: 0.27, y: 0.55, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.58, y: 0.34, type: 'object', visible: true, aim: [0.16, 0.08] },
            { id: 'object2', label: '第二子球', x: 0.74, y: 0.34, type: 'object2', visible: false, aim: [0.16, 0.08] }
        ],
        combo: [
            { id: 'cue', label: '母球', x: 0.22, y: 0.56, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.5, y: 0.48, type: 'object', visible: true, aim: [0.94, 0.12] },
            { id: 'object2', label: '第二子球', x: 0.64, y: 0.43, type: 'object2', visible: true, aim: [0.94, 0.08] }
        ]
    };
    return presets[practicePattern].map((ball) => ({ ...ball }));
};

const normalizeVector = (dx: number, dy: number): [number, number] => {
    const length = Math.hypot(dx, dy) || 1;
    return [dx / length, dy / length];
};

const toTableX = (x: number) => PLAYFIELD.left + x * PLAYFIELD.width;
const toTableY = (y: number) => PLAYFIELD.top + y * PLAYFIELD.height;
const toSvgX = (x: number) => toTableX(x) * 100;
const toSvgY = (y: number) => toTableY(y) * 50;
const PLAYFIELD_SVG_WIDTH = PLAYFIELD.width * 100;
const PLAYFIELD_SVG_HEIGHT = PLAYFIELD.height * 50;
const PLAYFIELD_SVG_LEFT = PLAYFIELD.left * 100;
const PLAYFIELD_SVG_TOP = PLAYFIELD.top * 50;
const BALL_DIAMETER_SVG = BALL_DIAMETER_REL * PLAYFIELD_SVG_WIDTH;
const toCssPoint = (x: number, y: number) => ({
    left: `${toTableX(x) * 100}%`,
    top: `${toTableY(y) * 100}%`
});

const getGhostBall = (object: PatternBall, aim: [number, number]): PatternGhostBall => {
    const dx = (aim[0] - object.x) * PLAYFIELD_SVG_WIDTH;
    const dy = (aim[1] - object.y) * PLAYFIELD_SVG_HEIGHT;
    const [ux, uy] = normalizeVector(dx, dy);
    return {
        x: clamp01(object.x - (ux * BALL_DIAMETER_SVG) / PLAYFIELD_SVG_WIDTH),
        y: clamp01(object.y - (uy * BALL_DIAMETER_SVG) / PLAYFIELD_SVG_HEIGHT),
        r: BALL_DIAMETER_SVG / 2
    };
};

const getCueLandingPoint = (
    cue: PatternBall,
    ghost: PatternGhostBall,
    object: PatternBall,
    stroke: StrokeControl
): [number, number] => {
    const [nx, ny] = normalizeVector(object.x - ghost.x, object.y - ghost.y);
    const [ix, iy] = normalizeVector(ghost.x - cue.x, ghost.y - cue.y);
    const normalComponent = ix * nx + iy * ny;
    const tangentX = ix - normalComponent * nx;
    const tangentY = iy - normalComponent * ny;
    const tangentLength = Math.hypot(tangentX, tangentY);
    const [tx, ty] = tangentLength > 0.001
        ? [tangentX / tangentLength, tangentY / tangentLength]
        : [-ny, nx];
    const [sx, sy] = getStrokeTipOffset(stroke);
    const powerPercent = getStrokePowerPercent(stroke);
    const distance = 0.07 + (powerPercent / 100) * 0.23;

    const forward = sy < 0 ? Math.abs(sy) : 0;
    const draw = sy > 0 ? sy : 0;
    const side = sx;
    const tangentDistance = tangentLength > 0.018 ? distance * (0.95 + Math.abs(side) * 0.18) : distance * 0.16;
    const followDistance = distance * forward * 0.72;
    const drawDistance = distance * draw * 0.92;
    const sideThrow = distance * side * 0.26;
    const baseX = ghost.x + tx * tangentDistance + nx * followDistance - nx * drawDistance - ny * sideThrow;
    const baseY = ghost.y + ty * tangentDistance + ny * followDistance - ny * drawDistance + nx * sideThrow;
    return [clamp01(baseX), clamp01(baseY)];
};

const buildPatternSegments = (
    practicePattern: PracticePattern,
    balls: PatternBall[],
    stroke: StrokeControl
): { segments: PatternRouteSegment[]; landing: [number, number]; ghostBalls: PatternGhostBall[] } => {
    const cue = balls.find((ball) => ball.id === 'cue') || balls[0];
    const object = balls.find((ball) => ball.id === 'object') || balls[1];
    const object2 = balls.find((ball) => ball.id === 'object2') || balls[2];

    // 使用 ball.aim 作為落袋目標，未設定則用預設落袋位置
    const defaultPocket1: [number, number] = practicePattern === 'bank' ? [0.16, 0.08] : [0.94, practicePattern === 'straight' ? object.y : 0.12];
    const pocket: [number, number] = object.aim ?? defaultPocket1;
    const pocket2: [number, number] = object2?.aim ?? [0.94, 0.08];

    // bank 模式：子球先擊岠再進袋，rail point 展向子球的 aim 橫向
    const railPoint: [number, number] = practicePattern === 'bank' && object.aim
        ? [object.aim[0] > 0.5 ? object.x + 0.15 : object.x - 0.15, object.aim[1]]
        : [object.x + 0.15, 0.08];

    const objectDirectionPoint = practicePattern === 'bank' ? railPoint : pocket;
    const primaryGhost = getGhostBall(object, objectDirectionPoint);
    const landing = getCueLandingPoint(cue, primaryGhost, object, stroke);
    const segments: PatternRouteSegment[] = [
        { type: 'cue_to_contact', points: [[cue.x, cue.y], [primaryGhost.x, primaryGhost.y]] }
    ];

    if (practicePattern === 'bank') {
        segments.push({ type: 'object_to_rail', points: [[object.x, object.y], railPoint] });
        segments.push({ type: 'object_to_pocket', points: [railPoint, pocket] });
    } else if (practicePattern === 'combo' && object2?.visible) {
        segments.push({ type: 'combo_transfer', points: [[object.x, object.y], [object2.x, object2.y]] });
        segments.push({ type: 'object_to_pocket', points: [[object2.x, object2.y], pocket2] });
    } else {
        segments.push({ type: 'object_to_pocket', points: [[object.x, object.y], pocket] });
    }

    segments.push({ type: 'cue_after_contact', points: [[primaryGhost.x, primaryGhost.y], landing] });
    return { segments, landing, ghostBalls: [primaryGhost] };
};

const createPatternLayout = (practicePattern: PracticePattern, stroke: StrokeControl): PatternLayout => {
    const balls = getPatternBalls(practicePattern);
    const { segments, landing, ghostBalls } = buildPatternSegments(practicePattern, balls, stroke);
    return { balls, route_segments: segments, cue_landing_point: landing, ghost_balls: ghostBalls, stroke };
};

export default function PracticePage({ onNavigate, metadata }: PracticePageProps) {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
    const [mode, setMode] = useState<PracticeMode>('menu');
    const [activePracticeTab, setActivePracticeTab] = useState<PracticeHomeTab>('recommendations');
    const [selectedPracticeType, setSelectedPracticeType] = useState<'single' | 'pattern' | null>(null);
    const [pattern, setPattern] = useState<PracticePattern>('straight');
    const [isActive, setIsActive] = useState(false);
    const [stats, setStats] = useState<PracticeStats>({ attempts: 0, successes: 0, success_rate: 0 });
    const [plannerView, setPlannerView] = useState<'best' | 'topn' | 'coach'>('best');
    const [plannerPlan, setPlannerPlan] = useState<MultiRoutePlan | null>(null);
    const [plannerLoading, setPlannerLoading] = useState(false);
    const [plannerError, setPlannerError] = useState('');
    const [lookaheadEnabled, setLookaheadEnabled] = useState(false);
    const lookaheadEnabledRef = useRef(false);
    const plannerPlanRef = useRef<MultiRoutePlan | null>(null);
    const selectedRouteIdRef = useRef<string | null>(null);
    const selectedRouteRef = useRef<RouteCandidate | null>(null);
    const [practiceStartLoading, setPracticeStartLoading] = useState(false);
    const [practiceStartError, setPracticeStartError] = useState('');
    const [strokePanelOpen, setStrokePanelOpen] = useState(false);
    const defaultStroke: StrokeControl = { tip: 'center', power: 'medium', power_percent: 50, tip_x: 0, tip_y: 0 };
    const [strokeControl, setStrokeControl] = useState<StrokeControl>(defaultStroke);
    const [patternGuideOptions, setPatternGuideOptions] = useState<PatternGuideOptions>({
        cue_laser_enabled: true,
        ball_guides_enabled: true
    });
    const [patternLayout, setPatternLayout] = useState<PatternLayout>(() => createPatternLayout('straight', defaultStroke));
    const [yoloDrawingMode, setYoloDrawingMode] = useState<YoloDrawingMode>('tactical');
    const [isApplyingYoloDrawing, setIsApplyingYoloDrawing] = useState(false);
    const [draggingPatternBall, setDraggingPatternBall] = useState<PatternBallId | null>(null);
    const [draggingPatternAim, setDraggingPatternAim] = useState<PatternBallId | null>(null);
    const [draggingPatternTip, setDraggingPatternTip] = useState(false);
    const [draggingSingleTip, setDraggingSingleTip] = useState(false);
    const patternTableRef = useRef<HTMLDivElement | null>(null);
    const patternCueBallRef = useRef<HTMLDivElement | null>(null);
    const singleCueBallRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        lookaheadEnabledRef.current = lookaheadEnabled;
    }, [lookaheadEnabled]);

    useEffect(() => {
        plannerPlanRef.current = plannerPlan;
    }, [plannerPlan]);

    const getRouteBallLabel = (route: RouteCandidate) => {
        const comboSecond = route.metadata?.combo_second_ball_number;
        if (route.route_type === 'combo' && typeof comboSecond === 'number') {
            return `${route.target_ball_number ?? '-'} → ${comboSecond}`;
        }
        return `${route.target_ball_number ?? '-'}`;
    };

    const getLookaheadSummary = (route: RouteCandidate) => {
        const lookahead = route.metadata?.lookahead;
        if (!lookahead || typeof lookahead !== 'object') return null;
        const payload = lookahead as Record<string, unknown>;
        const evaluation = typeof payload.evaluation === 'object' && payload.evaluation
            ? payload.evaluation as Record<string, unknown>
            : {};
        const finalScore = Number(evaluation.final_score ?? evaluation.score);
        const stateScore = Number(evaluation.state_score);
        const nextRoutes = Array.isArray(payload.next_routes)
            ? payload.next_routes as LookaheadNextRouteSummary[]
            : [];
        return {
            status: String(payload.status || '-'),
            finalScore: Number.isFinite(finalScore) ? finalScore : null,
            stateScore: Number.isFinite(stateScore) ? stateScore : null,
            nextRoute: nextRoutes[0] || null
        };
    };

    const getRouteDisplayName = (route: RouteCandidate) => {
        if (typeof route.metadata?.strategy_label === 'string') return route.metadata.strategy_label;
        return routeTypeLabel(route.route_type);
    };

    const formatPlannerPoint = (point?: number[] | null) => {
        if (!Array.isArray(point) || point.length < 2) return '-';
        return `${Math.round(Number(point[0]))},${Math.round(Number(point[1]))}`;
    };

    const formatPlannerPercent = (value?: number | null) => (
        typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(0)}%` : '-'
    );

    const renderLookaheadNextRoute = (route: RouteCandidate, compact = false) => {
        const nextRoute = getLookaheadSummary(route)?.nextRoute;
        if (!lookaheadEnabled || !nextRoute) return null;

        const landingPoint = nextRoute.cue_landing_point || nextRoute.cue_target_zone?.center || null;
        const strokeHint = nextRoute.stroke_hint;

        return (
            <div className={`practice-planner-next-step ${compact ? 'compact' : ''}`}>
                <span className="practice-planner-next-label">下一手</span>
                <strong>Ball {nextRoute.target_ball_number ?? '-'}</strong>
                <span>{nextRoute.strategy_label || routeTypeLabel(nextRoute.route_type)}</span>
                <span>進球 {formatPlannerPercent(nextRoute.success_prob ?? null)}</span>
                <span>走位 {formatPlannerPercent(nextRoute.position_success_prob ?? null)}</span>
                <span>落點 {formatPlannerPoint(landingPoint)}</span>
                {!compact && strokeHint && (
                    <span>{[strokeHint.type, strokeHint.power, strokeHint.spin].filter(Boolean).join(' / ') || '-'}</span>
                )}
            </div>
        );
    };

    const isPoint = (value: unknown): value is SvgPoint => (
        Array.isArray(value)
        && value.length >= 2
        && Number.isFinite(Number(value[0]))
        && Number.isFinite(Number(value[1]))
    );

    const pointValue = (value: unknown): SvgPoint | null => {
        if (!isPoint(value)) return null;
        return [Number(value[0]), Number(value[1])];
    };

    const pathFromPoints = (points: unknown) => {
        if (!Array.isArray(points)) return '';
        const clean = points.map(pointValue).filter((point): point is SvgPoint => Boolean(point));
        if (clean.length < 2) return '';
        return clean.map((point) => `${point[0]},${point[1]}`).join(' ');
    };

    const getYoloBoxInfo = (detection: Detection, index: number): PracticeYoloBox | null => {
        const confidence = detection.conf ?? detection.score ?? null;
        const label = detection.label || detection.color || `#${detection.number ?? index + 1}`;
        const number = typeof detection.number === 'number' ? detection.number : null;
        const color = detection.color || detection.label || null;

        if (detection.bbox && detection.bbox.length >= 4) {
            const [x1, y1, x2, y2] = detection.bbox;
            return {
                id: `${label}-${index}`,
                label,
                confidence,
                number,
                color,
                x: x1,
                y: y1,
                w: Math.max(0, x2 - x1),
                h: Math.max(0, y2 - y1)
            };
        }

        if (detection.x == null || detection.y == null || detection.w == null || detection.h == null) {
            return null;
        }

        return {
            id: `${label}-${index}`,
            label,
            confidence,
            number,
            color,
            x: detection.x,
            y: detection.y,
            w: detection.w,
            h: detection.h
        };
    };

    const getOverlayDetections = (): Detection[] => {
        const detections = [...(metadata?.detections_view || metadata?.detections || [])];
        const whiteBall = metadata?.white_ball;
        if (Array.isArray(whiteBall) && whiteBall.length >= 4) {
            const [x, y, w, h] = whiteBall.map(Number);
            const hasWhite = detections.some((detection) => {
                const box = getYoloBoxInfo(detection, -1);
                if (!box) return false;
                const label = String(box.label || box.color || '').toLowerCase();
                const isWhite = box.number === 0 || label.includes('white');
                const cx = box.x + box.w / 2;
                const cy = box.y + box.h / 2;
                const wcx = x + w / 2;
                const wcy = y + h / 2;
                return isWhite && Math.hypot(cx - wcx, cy - wcy) <= Math.max(w, h, box.w, box.h) * 0.55;
            });
            if (!hasWhite) {
                detections.unshift({ x, y, w, h, label: 'white ball', color: 'White', number: 0 });
            }
        }
        return detections;
    };

    const ballStrokeColor = (box: PracticeYoloBox) => {
        const number = box.number;
        if (number === 0) return '#f8fafc';
        if (number === 8) return '#111827';

        const byNumber: Record<number, string> = {
            1: '#facc15',
            2: '#2563eb',
            3: '#dc2626',
            4: '#7c3aed',
            5: '#f97316',
            6: '#16a34a',
            7: '#92400e',
            9: '#facc15',
            10: '#2563eb',
            11: '#dc2626',
            12: '#7c3aed',
            13: '#f97316',
            14: '#16a34a',
            15: '#92400e'
        };
        if (typeof number === 'number' && byNumber[number]) return byNumber[number];

        const colorName = String(box.color || box.label || '').toLowerCase();
        if (colorName.includes('white')) return '#f8fafc';
        if (colorName.includes('black')) return '#111827';
        if (colorName.includes('yellow')) return '#facc15';
        if (colorName.includes('blue')) return '#2563eb';
        if (colorName.includes('red')) return '#dc2626';
        if (colorName.includes('purple')) return '#7c3aed';
        if (colorName.includes('orange')) return '#f97316';
        if (colorName.includes('green')) return '#16a34a';
        if (colorName.includes('brown')) return '#92400e';
        return '#22d3ee';
    };

    const ballLabel = (box: PracticeYoloBox) => {
        if (box.number != null) return String(box.number);
        const colorName = String(box.color || box.label || '').toLowerCase();
        if (colorName.includes('white')) return 'W';
        if (colorName.includes('black')) return '8';
        return '';
    };

    const renderPracticeMetadataOverlay = () => {
        if (yoloDrawingMode === 'none') return null;
        const overlayWidth = metadata?.img_w || 1280;
        const overlayHeight = metadata?.img_h || 720;
        if (!metadata || !overlayWidth || !overlayHeight) return null;

        const yoloBoxes = getOverlayDetections()
            .map(getYoloBoxInfo)
            .filter((box): box is PracticeYoloBox => Boolean(box));
        const route = plannerPlan?.best_route || metadata.multi_plan?.best_route;
        const routeSegments = route?.route_segments || [];
        const positionPlay = route?.position_play;
        const cueAfter = positionPlay?.cue_ball_after_contact;
        const targetZone = cueAfter?.target_zone;
        const avoidZones = (cueAfter?.avoid_zones || [])
            .filter((zone) => zone.type !== 'pocket_scratch')
            .slice(0, 3);
        const visibleAvoidZones = yoloDrawingMode === 'full' ? avoidZones : [];
        const nextBallCenter = pointValue(positionPlay?.next_ball?.center);
        const lookaheadNextRoute = route ? getLookaheadSummary(route)?.nextRoute : null;
        const lookaheadSegments = lookaheadEnabled ? lookaheadNextRoute?.route_segments || [] : [];
        const lookaheadLanding = lookaheadEnabled ? pointValue(lookaheadNextRoute?.cue_landing_point) : null;
        const lookaheadZone = lookaheadEnabled ? lookaheadNextRoute?.cue_target_zone || lookaheadNextRoute?.cue_landing_zone : null;
        const lookaheadZoneCenter = pointValue(lookaheadZone?.center);
        const cueLaserLine = Array.isArray(metadata.cue_laser_line) ? metadata.cue_laser_line : [];
        const cueBox = Array.isArray(metadata.cue) && metadata.cue.length >= 4 ? metadata.cue : null;

        const segmentClass = (type: string) => {
            if (type === 'cue_to_contact' || type === 'cue_laser') return 'cue';
            if (type === 'cue_after_contact') return 'cue-after';
            if (type === 'combo_transfer') return 'combo';
            return 'object';
        };

        const hasOverlay = yoloBoxes.length > 0 || routeSegments.length > 0 || lookaheadSegments.length > 0 || targetZone || lookaheadZoneCenter || lookaheadLanding || visibleAvoidZones.length > 0 || cueLaserLine.length >= 2 || (yoloDrawingMode === 'full' && cueBox);
        if (!hasOverlay) return null;

        return (
            <svg
                className="practice-metadata-overlay"
                viewBox={`0 0 ${overlayWidth} ${overlayHeight}`}
                preserveAspectRatio="xMidYMid meet"
                aria-label="練習模式 metadata 前端疊圖"
            >
                {routeSegments.map((segment, index) => {
                    const points = pathFromPoints(segment.points);
                    if (!points) return null;
                    return (
                        <polyline
                            key={`practice-segment-${index}`}
                            className={`practice-route-segment ${segmentClass(segment.type)}`}
                            points={points}
                        />
                    );
                })}

                {cueLaserLine.length >= 2 && (
                    <polyline className="practice-cue-laser-line" points={pathFromPoints(cueLaserLine.slice(0, 2))} />
                )}

                {lookaheadSegments.map((segment, index) => {
                    const points = pathFromPoints(segment.points);
                    if (!points) return null;
                    return (
                        <polyline
                            key={`practice-lookahead-segment-${index}`}
                            className="practice-lookahead-route-segment"
                            points={points}
                        />
                    );
                })}

                {targetZone && pointValue(targetZone.center) && (
                    <g className="practice-zone target">
                        <circle
                            cx={pointValue(targetZone.center)?.[0]}
                            cy={pointValue(targetZone.center)?.[1]}
                            r={Number(targetZone.radius || 24)}
                        />
                        {yoloDrawingMode === 'full' && (
                            <text x={(pointValue(targetZone.center)?.[0] || 0) + Number(targetZone.radius || 24) + 8} y={(pointValue(targetZone.center)?.[1] || 0) + 6}>
                                TARGET
                            </text>
                        )}
                    </g>
                )}

                {visibleAvoidZones.map((zone, index) => {
                    const center = pointValue(zone.center);
                    if (!center) return null;
                    const radius = Number(zone.radius || 24);
                    return (
                        <g className="practice-zone avoid" key={`practice-avoid-${index}`}>
                            <circle cx={center[0]} cy={center[1]} r={radius} />
                            {yoloDrawingMode === 'full' && <text x={center[0] + radius + 8} y={center[1] + 6}>AVOID</text>}
                        </g>
                    );
                })}

                {nextBallCenter && (
                    <g className="practice-next-ball">
                        <circle cx={nextBallCenter[0]} cy={nextBallCenter[1]} r="18" />
                        {yoloDrawingMode === 'full' && (
                            <text x={nextBallCenter[0] + 22} y={nextBallCenter[1] - 8}>
                                NEXT {positionPlay?.next_ball?.number ?? ''}
                            </text>
                        )}
                    </g>
                )}

                {lookaheadZoneCenter && (
                    <g className="practice-lookahead-zone">
                        <circle
                            cx={lookaheadZoneCenter[0]}
                            cy={lookaheadZoneCenter[1]}
                            r={Number(lookaheadZone?.radius || 24)}
                        />
                        {yoloDrawingMode === 'full' && (
                            <text x={lookaheadZoneCenter[0] + Number(lookaheadZone?.radius || 24) + 8} y={lookaheadZoneCenter[1] + 6}>
                                2P TARGET
                            </text>
                        )}
                    </g>
                )}

                {lookaheadLanding && (
                    <g className="practice-lookahead-landing">
                        <circle cx={lookaheadLanding[0]} cy={lookaheadLanding[1]} r="15" />
                        <line x1={lookaheadLanding[0] - 11} y1={lookaheadLanding[1]} x2={lookaheadLanding[0] + 11} y2={lookaheadLanding[1]} />
                        <line x1={lookaheadLanding[0]} y1={lookaheadLanding[1] - 11} x2={lookaheadLanding[0]} y2={lookaheadLanding[1] + 11} />
                        {yoloDrawingMode === 'full' && (
                            <text x={lookaheadLanding[0] + 20} y={lookaheadLanding[1] - 10}>
                                2P NEXT {lookaheadNextRoute?.target_ball_number ?? ''}
                            </text>
                        )}
                    </g>
                )}

                {yoloDrawingMode === 'full' && cueBox && (
                    <g className="practice-cue-box">
                        <rect x={cueBox[0]} y={cueBox[1]} width={cueBox[2]} height={cueBox[3]} rx="3" />
                        {yoloDrawingMode === 'full' && <text x={cueBox[0]} y={Math.max(14, cueBox[1] - 6)}>CUE</text>}
                    </g>
                )}

                {yoloBoxes.map((box) => (
                    <g key={box.id}>
                        <circle
                            className="practice-yolo-bbox-rect"
                            style={{ stroke: ballStrokeColor(box) }}
                            cx={box.x + box.w / 2}
                            cy={box.y + box.h / 2}
                            r={Math.max(2, Math.min(box.w, box.h) / 2)}
                        />
                        {ballLabel(box) && (
                            <text
                                className="practice-ball-number-label"
                                x={box.x + box.w / 2}
                                y={box.y + box.h / 2}
                                textAnchor="middle"
                                dominantBaseline="central"
                            >
                                {ballLabel(box)}
                            </text>
                        )}
                        {yoloDrawingMode === 'full' && (
                            <text className="practice-yolo-bbox-label" x={box.x} y={Math.max(14, box.y - 6)}>
                                {box.label} {box.confidence != null ? box.confidence.toFixed(3) : '-'}
                            </text>
                        )}
                    </g>
                ))}
            </svg>
        );
    };

    const renderPositionPlaySummary = (route: RouteCandidate) => {
        const positionPlay = route.position_play;
        if (!positionPlay) return null;

        const nextBall = positionPlay.next_ball;
        const targetZone = positionPlay.cue_ball_after_contact?.target_zone;
        const expectedPoint = positionPlay.cue_ball_after_contact?.expected_point;
        const score = positionPlay.score;

        return (
            <div className="practice-planner-best-grid">
                <div>
                    <span>下一球</span>
                    <strong>{nextBall?.number ?? '-'}</strong>
                </div>
                <div>
                    <span>走位成功</span>
                    <strong>{score?.position_success_prob != null ? `${(score.position_success_prob * 100).toFixed(0)}%` : '-'}</strong>
                </div>
                <div>
                    <span>母球預估</span>
                    <strong>{expectedPoint ? `${expectedPoint[0]}, ${expectedPoint[1]}` : '-'}</strong>
                </div>
                <div>
                    <span>目標區</span>
                    <strong>{targetZone ? `${targetZone.center?.[0] ?? '-'}, ${targetZone.center?.[1] ?? '-'} / R${targetZone.radius}` : '-'}</strong>
                </div>
            </div>
        );
    };

    const getStrokeTipLabel = (tip: StrokeTip) => {
        const labels: Record<StrokeTip, string> = {
            center: '中桿',
            top: '高桿',
            draw: '低桿',
            left: '左塞',
            right: '右塞',
            top_left: '高桿+左塞',
            top_right: '高桿+右塞',
            draw_left: '低桿+左塞',
            draw_right: '低桿+右塞'
        };
        return labels[tip];
    };

    const getStrokePowerLabel = (power: StrokePower) => {
        const labels: Record<StrokePower, string> = {
            low: '小力',
            medium: '中力',
            medium_high: '中高力',
            high: '大力'
        };
        return labels[power];
    };

    const applyYoloDrawingMode = async (drawingMode: YoloDrawingMode) => {
        if (isApplyingYoloDrawing) return;

        setIsApplyingYoloDrawing(true);
        try {
            const response = await fetch(`${backendUrl}/api/control/overlay-mode`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: drawingMode })
            });
            if (!response.ok) throw new Error('切換標註顯示模式失敗');
            const data = await response.json();
            if (data.status !== 'success') throw new Error(data.message || '切換標註顯示模式失敗');
            setYoloDrawingMode(drawingMode);
        } catch (error) {
            console.error('Failed to apply YOLO drawing mode:', error);
        } finally {
            setIsApplyingYoloDrawing(false);
        }
    };

    const restoreLiveYoloDrawingMode = async () => {
        try {
            await fetch(`${backendUrl}/api/control/overlay-mode`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'full' })
            });
            setYoloDrawingMode('full');
        } catch (error) {
            console.error('Failed to restore live YOLO drawing mode:', error);
        }
    };

    // 玩家相關狀態
    const [playerName, setPlayerName] = useState('');
    const defaultPlayers = ['玩家1', '玩家2'];
    const [existingPlayers, setExistingPlayers] = useState<string[]>(defaultPlayers);

    // 錄影相關狀態
    const [isRecording, setIsRecording] = useState(false);
    const [gameId, setGameId] = useState<string | null>(null);
    const [recordingDuration, setRecordingDuration] = useState(0);
    const practiceActiveRef = useRef(false);
    const recordingRef = useRef(false);
    const gameIdRef = useRef<string | null>(null);
    const attemptsRef = useRef(0);
    const endingRef = useRef(false);
    const practicePollInFlightRef = useRef(false);
    const isPageVisibleRef = useRef(true);

    // 獲取已有玩家列表
    useEffect(() => {
        if (mode === 'player-setup') {
            fetchExistingPlayers();
        }
    }, [mode]);

    // 錄影計時器
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isRecording) {
            const startTime = Date.now();
            interval = setInterval(() => {
                setRecordingDuration(Math.floor((Date.now() - startTime) / 1000));
            }, 1000);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isRecording]);

    useEffect(() => {
        practiceActiveRef.current = isActive;
        recordingRef.current = isRecording;
        gameIdRef.current = gameId;
        attemptsRef.current = stats.attempts;
    }, [isActive, isRecording, gameId, stats.attempts]);

    useEffect(() => {
        if (mode === 'single' && metadata?.multi_plan) {
            let incomingPlan = metadata.multi_plan;
            const selectedRouteId = selectedRouteIdRef.current;
            if (selectedRouteId && incomingPlan.best_route?.id !== selectedRouteId) {
                incomingPlan = promotePlanRoute(incomingPlan, selectedRouteId, selectedRouteRef.current);
                if (incomingPlan.best_route?.id) {
                    selectedRouteIdRef.current = incomingPlan.best_route.id;
                    selectedRouteRef.current = incomingPlan.best_route;
                }
            }
            if (
                lookaheadEnabledRef.current &&
                planIncludesLookahead(plannerPlanRef.current) &&
                !planIncludesLookahead(incomingPlan)
            ) {
                return;
            }
            plannerPlanRef.current = incomingPlan;
            setPlannerPlan(incomingPlan);
        }
    }, [mode, metadata?.multi_plan]);

    useEffect(() => {
        if (mode !== 'single' && mode !== 'pattern') return;
        applyYoloDrawingMode('tactical');
    }, [mode]);

    useEffect(() => {
        if (selectedPracticeType !== 'pattern') return;
        setPatternLayout(createPatternLayout(pattern, patternLayout.stroke));
    }, [pattern, selectedPracticeType]);

    useEffect(() => {
        return () => {
            if (endingRef.current) return;
            if (!practiceActiveRef.current && !recordingRef.current) return;

            if (recordingRef.current && gameIdRef.current) {
                fetch('/api/recording/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        final_score: null,
                        winner: null,
                        total_rounds: attemptsRef.current
                    }),
                    keepalive: true
                }).catch(() => {});
            }

            fetch('/api/practice/end', { method: 'POST', keepalive: true }).catch(() => {});
        };
    }, []);

    // 追蹤頁面可見狀態，背景頁降頻
    useEffect(() => {
        const handleVisibilityChange = () => {
            isPageVisibleRef.current = !document.hidden;
        };

        handleVisibilityChange();
        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, []);

    // 輪詢練習狀態 (自動偵測用)
    useEffect(() => {
        let timer: number | null = null;
        let disposed = false;

        const pollPracticeState = async () => {
            if (disposed || !isActive || practicePollInFlightRef.current) {
                return;
            }

            practicePollInFlightRef.current = true;
            try {
                const response = await fetch('/api/practice/state');
                if (response.ok) {
                    const data = await response.json();
                    if (data.active !== false) {
                        setStats((prev) => {
                            const next = {
                                attempts: data.attempts,
                                successes: data.successes,
                                success_rate: data.success_rate || 0
                            };
                            if (
                                prev.attempts === next.attempts &&
                                prev.successes === next.successes &&
                                prev.success_rate === next.success_rate
                            ) {
                                return prev;
                            }
                            return next;
                        });
                    }
                }
            } catch (error) {
                console.error('Failed to fetch practice state:', error);
            } finally {
                practicePollInFlightRef.current = false;
            }
        };

        const scheduleNext = () => {
            if (disposed || !isActive) {
                return;
            }
            const delay = isPageVisibleRef.current ? 1500 : 4000;
            timer = window.setTimeout(async () => {
                await pollPracticeState();
                scheduleNext();
            }, delay);
        };

        if (isActive) {
            pollPracticeState();
            scheduleNext();
        }

        return () => {
            disposed = true;
            if (timer !== null) {
                clearTimeout(timer);
            }
        };
    }, [isActive]);

    const fetchExistingPlayers = async () => {
        try {
            const response = await fetch('/api/stats/summary');
            if (response.ok) {
                const data = await response.json();
                if (data.player_rankings) {
                    const players = data.player_rankings.map((p: any) => p.name);
                    setExistingPlayers(Array.from(new Set([...defaultPlayers, ...players])));
                }
            }
        } catch (error) {
            console.error('Failed to fetch players:', error);
        }
    };

    // 格式化錄影時長
    const formatDuration = (seconds: number): string => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    // 處理練習類型選擇
    const handleSelectPracticeType = (type: 'single' | 'pattern') => {
        setSelectedPracticeType(type);
        if (type === 'pattern') {
            setPatternLayout(createPatternLayout(pattern, patternLayout.stroke));
        }
        setMode('player-setup');
    };

    const updatePatternLayout = (balls: PatternBall[], stroke: StrokeControl = patternLayout.stroke) => {
        const { segments, landing, ghostBalls } = buildPatternSegments(pattern, balls, stroke);
        setPatternLayout({
            balls,
            route_segments: segments,
            cue_landing_point: landing,
            ghost_balls: ghostBalls,
            stroke
        });
    };

    const handlePatternPointerMove = (event: PointerEvent<HTMLDivElement>) => {
        if (!patternTableRef.current) return;
        const rect = patternTableRef.current.getBoundingClientRect();
        const rawX = (event.clientX - rect.left) / rect.width;
        const rawY = (event.clientY - rect.top) / rect.height;
        const x = clamp01((rawX - PLAYFIELD.left) / PLAYFIELD.width);
        const y = clamp01((rawY - PLAYFIELD.top) / PLAYFIELD.height);

        if (draggingPatternBall) {
            // 拖曳球位置
            const nextBalls = patternLayout.balls.map((ball) =>
                ball.id === draggingPatternBall ? { ...ball, x, y } : ball
            );
            // straight 模式下移動子球時同步更新 aim.y 保持直線對齊
            if (pattern === 'straight' && draggingPatternBall === 'object') {
                const movedBall = nextBalls.find(b => b.id === 'object');
                if (movedBall && movedBall.aim) {
                    movedBall.aim = [movedBall.aim[0], y];
                }
            }
            updatePatternLayout(nextBalls);
        } else if (draggingPatternAim) {
            // 拖曳落袋目標點
            const nextBalls = patternLayout.balls.map((ball) =>
                ball.id === draggingPatternAim ? { ...ball, aim: [x, y] as [number, number] } : ball
            );
            updatePatternLayout(nextBalls);
        }
    };

    const handlePatternStrokeChange = (nextStroke: StrokeControl) => {
        updatePatternLayout(patternLayout.balls, nextStroke);
    };

    const getPatternTipOffsetFromPointer = (event: PointerEvent<HTMLElement>): [number, number] => {
        const cueBall = patternCueBallRef.current;
        if (!cueBall) return getStrokeTipOffset(patternLayout.stroke);
        const rect = cueBall.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        let nx = (event.clientX - centerX) / (rect.width * 0.42);
        let ny = (event.clientY - centerY) / (rect.height * 0.42);
        const length = Math.hypot(nx, ny);
        if (length > 1) {
            nx /= length;
            ny /= length;
        }
        return [Math.round(nx * 100) / 100, Math.round(ny * 100) / 100];
    };

    const updatePatternTipFromPointer = (event: PointerEvent<HTMLElement>) => {
        const [tipX, tipY] = getPatternTipOffsetFromPointer(event);
        const tip = getLegacyTipFromOffset(tipX, tipY);
        const [currentX, currentY] = getStrokeTipOffset(patternLayout.stroke);
        if (tip !== patternLayout.stroke.tip || tipX !== currentX || tipY !== currentY) {
            handlePatternStrokeChange({ ...patternLayout.stroke, tip, tip_x: tipX, tip_y: tipY });
        }
    };

    const handlePatternPowerPercent = (percent: number) => {
        const powerPercent = Math.max(1, Math.min(100, Math.round(percent)));
        const power = getPowerFromPercent(powerPercent);
        handlePatternStrokeChange({ ...patternLayout.stroke, power, power_percent: powerPercent });
    };

    const handleResetPatternStroke = () => {
        handlePatternStrokeChange(defaultStroke);
    };

    const getSingleTipOffsetFromPointer = (event: PointerEvent<HTMLElement>): [number, number] => {
        const cueBall = singleCueBallRef.current;
        if (!cueBall) return getStrokeTipOffset(strokeControl);
        const rect = cueBall.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        let nx = (event.clientX - centerX) / (rect.width * 0.42);
        let ny = (event.clientY - centerY) / (rect.height * 0.42);
        const length = Math.hypot(nx, ny);
        if (length > 1) {
            nx /= length;
            ny /= length;
        }
        return [Math.round(nx * 100) / 100, Math.round(ny * 100) / 100];
    };

    const updateSingleTipFromPointer = (event: PointerEvent<HTMLElement>) => {
        const [tipX, tipY] = getSingleTipOffsetFromPointer(event);
        const tip = getLegacyTipFromOffset(tipX, tipY);
        const [currentX, currentY] = getStrokeTipOffset(strokeControl);
        if (tip !== strokeControl.tip || tipX !== currentX || tipY !== currentY) {
            handleApplyStroke({ ...strokeControl, tip, tip_x: tipX, tip_y: tipY });
        }
    };

    const handleSinglePowerPercent = (percent: number) => {
        const powerPercent = Math.max(1, Math.min(100, Math.round(percent)));
        const power = getPowerFromPercent(powerPercent);
        if (power !== strokeControl.power || powerPercent !== getStrokePowerPercent(strokeControl)) {
            handleApplyStroke({ ...strokeControl, power, power_percent: powerPercent });
        }
    };

    const handleResetSingleStroke = () => {
        handleApplyStroke({
            tip: 'center',
            tip_x: 0,
            tip_y: 0,
            power: 'medium',
            power_percent: 50
        });
    };

    // 問題3修復：改傳相對座標(0~1)，後端負責用 calibrator.projection_bounds 做校正轉換
    const buildPatternProjectionPayload = () => ({
        coordinate_space: 'relative',
        balls: patternLayout.balls
            .filter((ball) => ball.visible)
            .map((ball) => ({
                x: ball.x,
                y: ball.y,
                r: 24,
                type: ball.type,
                label: ball.label
            })),
        route_segments: patternLayout.route_segments.map((segment) => ({
            type: segment.type,
            points: segment.points
        })),
        cue_landing_point: patternLayout.cue_landing_point,
        ghost_balls: patternLayout.ghost_balls,
        stroke: patternLayout.stroke,
        guide_options: patternGuideOptions
    });

    const handlePatternGuideToggle = async (key: keyof PatternGuideOptions, enabled: boolean) => {
        const nextOptions = { ...patternGuideOptions, [key]: enabled };
        setPatternGuideOptions(nextOptions);

        if (!isActive || (mode !== 'pattern' && mode !== 'single')) {
            return;
        }

        try {
            const response = await fetch('/api/practice/guides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ guide_options: nextOptions })
            });

            if (!response.ok) {
                throw new Error('更新練習指引失敗');
            }
        } catch (error) {
            console.error('Failed to update practice guide options:', error);
            setPatternGuideOptions(patternGuideOptions);
        }
    };

    // 開始練習
    const fetchWithTimeout = async (url: string, options: RequestInit, timeoutMs = 10000) => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        try {
            return await fetch(url, { ...options, signal: controller.signal });
        } finally {
            clearTimeout(timeout);
        }
    };

    const handleStartPractice = async (skipPlayer: boolean = false) => {
        if (practiceStartLoading) return;
        setPracticeStartLoading(true);
        setPracticeStartError('');
        try {
            if (!selectedPracticeType) {
                throw new Error('請先選擇練習類型');
            }
            const finalPlayerName = skipPlayer ? '' : playerName;
            const practiceType = selectedPracticeType === 'single' ? 'practice_single' : 'practice_pattern';

            // 啟動練習
            const response = await fetchWithTimeout(`${backendUrl}/api/practice/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: selectedPracticeType,
                    pattern: selectedPracticeType === 'pattern' ? pattern : null,
                    player_name: finalPlayerName,
                    pattern_layout: selectedPracticeType === 'pattern' ? buildPatternProjectionPayload() : null,
                    guide_options: {
                        cue_laser_enabled: patternGuideOptions.cue_laser_enabled
                    }
                })
            }, 10000);

            if (response.ok) {
                // 啟動錄影
                try {
                    const recordingResponse = await fetchWithTimeout(`${backendUrl}/api/recording/start`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            game_type: practiceType,
                            players: finalPlayerName ? [finalPlayerName] : []
                        })
                    }, 6000);

                    if (recordingResponse.ok) {
                        const recordingData = await recordingResponse.json();
                        setGameId(recordingData.game_id);
                        setIsRecording(true);
                        console.log('錄影已啟動:', recordingData.game_id);
                    }
                } catch (recordingError) {
                    console.warn('錄影啟動失敗:', recordingError);
                }

                selectedRouteIdRef.current = null;
                selectedRouteRef.current = null;
                plannerPlanRef.current = null;
                setPlannerPlan(null);
                setPlannerError('');
                setPlannerView('best');
                setMode(selectedPracticeType!);
                setIsActive(true);
                setStats({ attempts: 0, successes: 0, success_rate: 0 });
            } else {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.detail || errorData?.message || `開始練習失敗 (${response.status})`);
            }
        } catch (error) {
            console.error('Failed to start practice:', error);
            const message = error instanceof Error && error.name === 'AbortError'
                ? '後端沒有回應，請重新啟動後端後再開始練習'
                : error instanceof Error
                    ? error.message
                    : '開始練習失敗';
            setPracticeStartError(message);
        } finally {
            setPracticeStartLoading(false);
        }
    };

    // 記錄練習結果
    const handleRecordAttempt = async (success: boolean) => {
        try {
            const response = await fetch('/api/practice/record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ success })
            });

            if (response.ok) {
                const data = await response.json();
                setStats(data);
            }
        } catch (error) {
            console.error('Failed to record attempt:', error);
        }
    };

    const handleRunPlanner = async (nextLookaheadEnabled = lookaheadEnabledRef.current) => {
        lookaheadEnabledRef.current = nextLookaheadEnabled;
        setPlannerLoading(true);
        setPlannerError('');

        try {
            const response = await fetch(`${backendUrl}/api/planner/plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rule_profile: 'practice',
                    top_n: 5,
                    max_bounces: 3,
                    combo_depth: 2,
                    lookahead_enabled: nextLookaheadEnabled,
                    lookahead_ply: 2,
                    lookahead_candidate_count: 5,
                    lookahead_next_top_n: 3,
                    lookahead_score_weight: 0.25,
                    stroke: strokeControl
                })
            });

            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data?.error?.message || data?.message || '多球規劃啟動失敗');
            }

            const selectedRouteId = typeof data.multi_plan?.selected_route_id === 'string'
                ? data.multi_plan.selected_route_id
                : null;
            selectedRouteIdRef.current = selectedRouteId;
            selectedRouteRef.current = selectedRouteId && data.multi_plan?.best_route ? data.multi_plan.best_route : null;
            const nextPlan = selectedRouteId ? promotePlanRoute(data.multi_plan, selectedRouteId, selectedRouteRef.current) : data.multi_plan;
            plannerPlanRef.current = nextPlan;
            setPlannerPlan(nextPlan);
        } catch (error) {
            const message = error instanceof Error ? error.message : '多球規劃啟動失敗';
            setPlannerError(message);
        } finally {
            setPlannerLoading(false);
        }
    };

    const handleLookaheadToggle = (enabled: boolean) => {
        lookaheadEnabledRef.current = enabled;
        setLookaheadEnabled(enabled);
        if (isActive && plannerPlan && !plannerLoading) {
            void handleRunPlanner(enabled);
        }
    };

    const handleApplyStroke = async (nextStroke: StrokeControl = strokeControl) => {
        setStrokeControl(nextStroke);
        if (!isActive) return;

        setPlannerLoading(true);
        setPlannerError('');

        try {
            const response = await fetch(`${backendUrl}/api/planner/stroke`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    stroke: nextStroke,
                    lookahead_enabled: lookaheadEnabledRef.current,
                    lookahead_ply: 2,
                    lookahead_candidate_count: 5,
                    lookahead_next_top_n: 3,
                    lookahead_score_weight: 0.25
                })
            });

            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data?.error?.message || data?.message || '桿法套用失敗');
            }

            const selectedRouteId = selectedRouteIdRef.current;
            const nextPlan = selectedRouteId ? promotePlanRoute(data.multi_plan, selectedRouteId, selectedRouteRef.current) : data.multi_plan;
            if (selectedRouteId && nextPlan.best_route?.id) {
                selectedRouteIdRef.current = nextPlan.best_route.id;
                selectedRouteRef.current = nextPlan.best_route;
            }
            plannerPlanRef.current = nextPlan;
            setPlannerPlan(nextPlan);
        } catch (error) {
            const message = error instanceof Error ? error.message : '桿法套用失敗';
            setPlannerError(message);
        } finally {
            setPlannerLoading(false);
        }
    };

    const handleSelectRoute = async (route: RouteCandidate) => {
        if (!route.id) return;

        selectedRouteIdRef.current = route.id;
        selectedRouteRef.current = route;
        if (plannerPlanRef.current) {
            const promotedPlan = promotePlanRoute(plannerPlanRef.current, route.id, route);
            plannerPlanRef.current = promotedPlan;
            setPlannerPlan(promotedPlan);
        }
        setPlannerLoading(true);
        setPlannerError('');

        try {
            const response = await fetch(`${backendUrl}/api/planner/select-route`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ route_id: route.id })
            });

            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data?.error?.message || data?.message || '切換進球線路失敗');
            }

            selectedRouteIdRef.current = route.id;
            selectedRouteRef.current = route;
            const nextPlan = promotePlanRoute(data.multi_plan, route.id, route);
            if (nextPlan.best_route?.id) {
                selectedRouteIdRef.current = nextPlan.best_route.id;
                selectedRouteRef.current = nextPlan.best_route;
            }
            plannerPlanRef.current = nextPlan;
            setPlannerPlan(nextPlan);
        } catch (error) {
            const message = error instanceof Error ? error.message : '切換進球線路失敗';
            setPlannerError(message);
        } finally {
            setPlannerLoading(false);
        }
    };

    // 結束練習
    const handleEndPractice = async () => {
        try {
            endingRef.current = true;
            // 停止錄影
            if (isRecording && gameId) {
                await fetch('/api/recording/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        final_score: null,
                        winner: null,
                        total_rounds: stats.attempts
                    })
                });
                setIsRecording(false);
                setGameId(null);
                setRecordingDuration(0);
            }

            await fetch('/api/practice/end', { method: 'POST' });
            await restoreLiveYoloDrawingMode();
            selectedRouteIdRef.current = null;
            selectedRouteRef.current = null;
            plannerPlanRef.current = null;
            setIsActive(false);
            setPlannerPlan(null);
            setMode('menu');
            setPlayerName('');
            setSelectedPracticeType(null);
        } catch (error) {
            console.error('Failed to end practice:', error);
        }
    };

    // 返回選單
    const handleBackToMenu = () => {
        handleEndPractice();
    };

    // 渲染選單
    if (mode === 'menu') {
        return (
            <div className="practice-page">
                <div className="practice-header">
                    <h1>訓練中心</h1>
                    <p>選擇訓練內容，追蹤技巧成長與 AI 分析結果</p>
                </div>

                <div className="practice-home-tabs" role="tablist" aria-label="訓練頁分頁">
                    {practiceHomeTabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            className={`practice-home-tab ${activePracticeTab === tab.id ? 'active' : ''}`}
                            onClick={() => setActivePracticeTab(tab.id)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {activePracticeTab === 'recommendations' ? (
                    <>
                        <div className="practice-recommendation-grid">
                            {trainingRecommendations.map((item) => (
                                <article
                                    className="practice-recommendation-card"
                                    key={item.title}
                                    onClick={() => handleSelectPracticeType(item.practiceType)}
                                >
                                    <div className={`practice-card-visual ${item.visual}`} aria-hidden="true">
                                        <span />
                                        <span />
                                        <span />
                                    </div>
                                    <div className="practice-card-copy">
                                        <h2>{item.title}</h2>
                                        <p>{item.description}</p>
                                    </div>
                                    <div className="practice-card-tags">
                                        {item.tags.map((tag) => (
                                            <span key={tag}>{tag}</span>
                                        ))}
                                    </div>
                                    <button
                                        className="practice-card-action"
                                        type="button"
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            handleSelectPracticeType(item.practiceType);
                                        }}
                                    >
                                        {item.actionLabel}
                                    </button>
                                </article>
                            ))}
                        </div>

                        <section className="practice-weekly-overview" aria-label="本週訓練總覽">
                            <div className="practice-section-heading">
                                <h2>本週訓練總覽</h2>
                                <p>快速掌握近期訓練量、準度與 AI 評分。</p>
                            </div>
                            <div className="practice-weekly-grid">
                                {weeklyTrainingStats.map((stat) => (
                                    <div className="practice-weekly-card" key={stat.label}>
                                        <span>{stat.label}</span>
                                        <strong>{stat.value}</strong>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </>
                ) : (
                    <section className="practice-placeholder-panel">
                        <h2>{practiceHomeTabs.find((tab) => tab.id === activePracticeTab)?.label}</h2>
                        <p>內容建置中</p>
                    </section>
                )}

                <div className="practice-footer">
                    <button className="btn-secondary" onClick={() => onNavigate('stream')}>
                        返回即時影像
                    </button>
                </div>
            </div>
        );
    }

    // 渲染玩家設定頁面
    if (mode === 'player-setup') {
        return (
            <div className="practice-page">
                <div className="practice-header">
                    <button className="btn-back" onClick={() => setMode('menu')}>
                        ← 返回
                    </button>
                    <h1>練習模式 - {selectedPracticeType === 'single' ? '一般練習' : '球型練習'}</h1>
                </div>

                <div className="player-setup-container">
                    <div className="player-setup-section">
                        <h2>玩家資訊</h2>
                        <div className="player-input-group">
                            <label>玩家名稱</label>
                            <input
                                type="text"
                                value={playerName}
                                onChange={(e) => setPlayerName(e.target.value)}
                                placeholder="輸入玩家名稱..."
                                maxLength={20}
                            />
                        </div>

                        <div className="player-selector-group">
                            <label>或選擇已有玩家：</label>
                            <div className="player-selector-scroll">
                                {existingPlayers.map((player) => (
                                    <button
                                        key={player}
                                        className={`player-button ${playerName === player ? 'selected' : ''}`}
                                        onClick={() => setPlayerName(player)}
                                    >
                                        {player}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <p className="setup-hint">提示：填寫玩家名稱以記錄統計</p>
                    </div>

                    {selectedPracticeType === 'pattern' && (
                        <div className="pattern-setup-section">
                            <h2>球型練習類型</h2>
                            <div className="pattern-buttons">
                                <button
                                    className={`pattern-btn ${pattern === 'straight' ? 'active' : ''}`}
                                    onClick={() => setPattern('straight')}
                                >
                                    直線球
                                </button>
                                <button
                                    className={`pattern-btn ${pattern === 'cut' ? 'active' : ''}`}
                                    onClick={() => setPattern('cut')}
                                >
                                    切球
                                </button>
                                <button
                                    className={`pattern-btn ${pattern === 'bank' ? 'active' : ''}`}
                                    onClick={() => setPattern('bank')}
                                >
                                    反彈球
                                </button>
                                <button
                                    className={`pattern-btn ${pattern === 'combo' ? 'active' : ''}`}
                                    onClick={() => setPattern('combo')}
                                >
                                    組合球
                                </button>
                            </div>

                            <div className="pattern-table-builder">
                                <div className="pattern-builder-header">
                                    <h3>球檯設定</h3>
                                    <div className="pattern-builder-summary">
                                        {getStrokeTipLabel(patternLayout.stroke.tip)} / {getStrokePowerLabel(patternLayout.stroke.power)}
                                    </div>
                                </div>
                                <div className="pattern-guide-toggles">
                                    <label className="pattern-toggle">
                                        <input
                                            type="checkbox"
                                            checked={patternGuideOptions.cue_laser_enabled}
                                            onChange={(event) => handlePatternGuideToggle('cue_laser_enabled', event.target.checked)}
                                        />
                                        <span>球桿雷射指引線</span>
                                    </label>
                                    <label className="pattern-toggle">
                                        <input
                                            type="checkbox"
                                            checked={patternGuideOptions.ball_guides_enabled}
                                            onChange={(event) => handlePatternGuideToggle('ball_guides_enabled', event.target.checked)}
                                        />
                                        <span>母球子球指引線</span>
                                    </label>
                                </div>

                                {/* 問題1修復：用 SVG overlay 精確繪製從球心到球心的路線 */}
                                <div
                                    className="pattern-virtual-table"
                                    ref={patternTableRef}
                                    onPointerMove={handlePatternPointerMove}
                                    onPointerUp={() => {
                                        setDraggingPatternBall(null);
                                        setDraggingPatternAim(null);
                                    }}
                                    onPointerLeave={() => {
                                        setDraggingPatternBall(null);
                                        setDraggingPatternAim(null);
                                    }}
                                >
                                    <div className="pattern-table-felt" aria-hidden="true" />
                                    {['tl', 'tc', 'tr', 'bl', 'bc', 'br'].map((pocket) => (
                                        <span key={pocket} className={`pattern-pocket ${pocket}`} aria-hidden="true" />
                                    ))}
                                    {[14, 28, 42, 58, 72, 86].map((x) => (
                                        <span key={`top-${x}`} className="pattern-diamond top" style={{ left: `${x}%` }} aria-hidden="true" />
                                    ))}
                                    {[14, 28, 42, 58, 72, 86].map((x) => (
                                        <span key={`bottom-${x}`} className="pattern-diamond bottom" style={{ left: `${x}%` }} aria-hidden="true" />
                                    ))}
                                    {[24, 50, 76].map((y) => (
                                        <span key={`left-${y}`} className="pattern-diamond left" style={{ top: `${y}%` }} aria-hidden="true" />
                                    ))}
                                    {[24, 50, 76].map((y) => (
                                        <span key={`right-${y}`} className="pattern-diamond right" style={{ top: `${y}%` }} aria-hidden="true" />
                                    ))}
                                    <div className="pattern-table-rail top" />
                                    <div className="pattern-table-rail bottom" />
                                    <div className="pattern-table-rail left" />
                                    <div className="pattern-table-rail right" />

                                    {/* SVG 路線層：viewBox 100x50 對應 2:1 球檯，避免圓形標記被拉扁 */}
                                    <svg
                                        className="pattern-route-svg"
                                        viewBox="0 0 100 50"
                                        preserveAspectRatio="none"
                                        aria-hidden="true"
                                    >
                                        <defs>
                                            <clipPath id="pattern-playfield-clip">
                                                <rect
                                                    x={PLAYFIELD_SVG_LEFT}
                                                    y={PLAYFIELD_SVG_TOP}
                                                    width={PLAYFIELD_SVG_WIDTH}
                                                    height={PLAYFIELD_SVG_HEIGHT}
                                                />
                                            </clipPath>
                                        </defs>
                                        <g clipPath="url(#pattern-playfield-clip)">
                                        {/* 路線線段 */}
                                        {patternGuideOptions.ball_guides_enabled && patternLayout.route_segments.map((segment, segIdx) =>
                                            segment.points.slice(1).map((endPoint, ptIdx) => {
                                                const startPoint = segment.points[ptIdx];
                                                const colorMap: Record<string, string> = {
                                                    cue_to_contact: '#FFFFFF',
                                                    object_to_pocket: '#56E06F',
                                                    object_to_rail: '#56E06F',
                                                    object_after_contact: '#56E06F',
                                                    combo_transfer: '#FFD24A',
                                                    cue_after_contact: '#43D5FF',
                                                };
                                                return (
                                                    <line
                                                        key={`${segment.type}-${segIdx}-${ptIdx}`}
                                                        x1={toSvgX(startPoint[0])}
                                                        y1={toSvgY(startPoint[1])}
                                                        x2={toSvgX(endPoint[0])}
                                                        y2={toSvgY(endPoint[1])}
                                                        stroke={colorMap[segment.type] ?? '#FFFFFF'}
                                                        strokeWidth="1.6"
                                                        strokeLinecap="round"
                                                        strokeDasharray={segment.type === 'cue_after_contact' ? '3 2' : undefined}
                                                    />
                                                );
                                            })
                                        )}
                                        {/* 母球落點圓圈 + 十字 */}
                                        {patternGuideOptions.ball_guides_enabled && patternLayout.ghost_balls.map((ghostBall, index) => (
                                            <g key={`ghost-${index}`}>
                                                <circle
                                                    cx={toSvgX(ghostBall.x)}
                                                    cy={toSvgY(ghostBall.y)}
                                                    r={ghostBall.r}
                                                    fill="rgba(255,255,255,0.08)"
                                                    stroke="#FFFFFF"
                                                    strokeWidth="0.75"
                                                    strokeDasharray="1.6 1.2"
                                                />
                                                <circle
                                                    cx={toSvgX(ghostBall.x)}
                                                    cy={toSvgY(ghostBall.y)}
                                                    r="0.75"
                                                    fill="#FFFFFF"
                                                />
                                            </g>
                                        ))}

                                        {/* 母球落點圓圈 + 十字 */}
                                        {patternGuideOptions.ball_guides_enabled && (
                                            <>
                                                <circle
                                                    cx={toSvgX(patternLayout.cue_landing_point[0])}
                                                    cy={toSvgY(patternLayout.cue_landing_point[1])}
                                                    r="3"
                                                    fill="none"
                                                    stroke="#43D5FF"
                                                    strokeWidth="0.9"
                                                />
                                                <line
                                                    x1={toSvgX(patternLayout.cue_landing_point[0]) - 2.2}
                                                    y1={toSvgY(patternLayout.cue_landing_point[1])}
                                                    x2={toSvgX(patternLayout.cue_landing_point[0]) + 2.2}
                                                    y2={toSvgY(patternLayout.cue_landing_point[1])}
                                                    stroke="#43D5FF" strokeWidth="0.9"
                                                />
                                                <line
                                                    x1={toSvgX(patternLayout.cue_landing_point[0])}
                                                    y1={toSvgY(patternLayout.cue_landing_point[1]) - 2.2}
                                                    x2={toSvgX(patternLayout.cue_landing_point[0])}
                                                    y2={toSvgY(patternLayout.cue_landing_point[1]) + 2.2}
                                                    stroke="#43D5FF" strokeWidth="0.9"
                                                />
                                            </>
                                        )}

                                        {/* 落袋目標點 (aim)：菱形可拖曳標記 */}
                                        {patternGuideOptions.ball_guides_enabled && patternLayout.balls
                                            .filter((b) => b.visible && b.type !== 'cue' && b.aim)
                                            .map((ball) => {
                                                const ax = toSvgX(ball.aim![0]);
                                                const ay = toSvgY(ball.aim![1]);
                                                const r = 3;
                                                const isAiming = draggingPatternAim === ball.id;
                                                return (
                                                    <g
                                                        key={`aim-${ball.id}`}
                                                        style={{ cursor: 'crosshair', pointerEvents: 'all' }}
                                                        onPointerDown={(e) => {
                                                            e.stopPropagation();
                                                            setDraggingPatternAim(ball.id);
                                                            setDraggingPatternBall(null);
                                                        }}
                                                        onPointerUp={() => setDraggingPatternAim(null)}
                                                    >
                                                        {/* 可點擊熱區（放大感應範圍） */}
                                                        <circle cx={ax} cy={ay} r={r * 4} fill="transparent" />
                                                        {/* 圓形落袋目標 */}
                                                        <circle
                                                            cx={ax}
                                                            cy={ay}
                                                            r={r * 1.35}
                                                            fill={isAiming ? '#FFD24A' : 'rgba(255,210,74,0.22)'}
                                                            stroke="#FFD24A"
                                                            strokeWidth="0.8"
                                                        />
                                                        {/* 落袋標記 × */}
                                                        <line x1={ax - 1.5} y1={ay - 1.5} x2={ax + 1.5} y2={ay + 1.5} stroke="#FFD24A" strokeWidth="0.7" />
                                                        <line x1={ax + 1.5} y1={ay - 1.5} x2={ax - 1.5} y2={ay + 1.5} stroke="#FFD24A" strokeWidth="0.7" />
                                                        {/* 子球到落袋的虚線連接線 */}
                                                        {patternGuideOptions.ball_guides_enabled && (
                                                            <line
                                                                x1={toSvgX(ball.x)} y1={toSvgY(ball.y)}
                                                                x2={ax} y2={ay}
                                                                stroke="rgba(255,210,74,0.35)"
                                                                strokeWidth="0.6"
                                                                strokeDasharray="2 1.5"
                                                            />
                                                        )}
                                                    </g>
                                                );
                                            })
                                        }
                                        </g>
                                    </svg>

                                    {/* 可拖曳球 */}
                                    {patternLayout.balls.filter((ball) => ball.visible).map((ball) => (
                                        <button
                                            key={ball.id}
                                            type="button"
                                            className={`pattern-draggable-ball ${ball.type}${draggingPatternBall === ball.id ? ' dragging' : ''}`}
                                            style={toCssPoint(ball.x, ball.y)}
                                            onPointerDown={(event) => {
                                                event.currentTarget.setPointerCapture(event.pointerId);
                                                setDraggingPatternBall(ball.id);
                                            }}
                                            onPointerUp={() => {
                                                setDraggingPatternBall(null);
                                                setDraggingPatternAim(null);
                                            }}
                                            aria-label={`移動${ball.label}`}
                                            title={`拖曳移動${ball.label}，落袋目標點(菱形)可獨立拖曳調整方向`}
                                        >
                                            {ball.type === 'cue' ? '' : ball.type === 'object2' ? '2' : '1'}
                                        </button>
                                    ))}
                                </div>

                                {/* 問題2修復：視覺化桿法 + 力量UI */}
                                <div className="pattern-stroke-ui">
                                    {/* 左側：視覺化母球桿法選擇 */}
                                    <div className="pattern-cue-wrap">
                                        <div className="pattern-control-header">
                                            <div className="pattern-cue-label">母球桿法</div>
                                            <button
                                                type="button"
                                                className="pattern-reset-button"
                                                onClick={handleResetPatternStroke}
                                            >
                                                重置
                                            </button>
                                        </div>
                                        <div
                                            className="pattern-cue-ball"
                                            ref={patternCueBallRef}
                                            onPointerDown={(event) => {
                                                event.currentTarget.setPointerCapture(event.pointerId);
                                                setDraggingPatternTip(true);
                                                updatePatternTipFromPointer(event);
                                            }}
                                            onPointerMove={(event) => {
                                                if (draggingPatternTip) updatePatternTipFromPointer(event);
                                            }}
                                            onPointerUp={(event) => {
                                                event.currentTarget.releasePointerCapture(event.pointerId);
                                                setDraggingPatternTip(false);
                                            }}
                                            onPointerCancel={() => setDraggingPatternTip(false)}
                                            role="slider"
                                            aria-label="母球撞點"
                                            aria-valuetext={getStrokeTipLabel(patternLayout.stroke.tip)}
                                            title="拖曳紅點調整母球撞點"
                                        >
                                            <span className="cue-cross horizontal" aria-hidden="true" />
                                            <span className="cue-cross vertical" aria-hidden="true" />
                                            <span className="cue-equator" aria-hidden="true" />
                                            <span
                                                className="cue-dot-indicator"
                                                style={getTipDotStyle(patternLayout.stroke)}
                                                aria-hidden="true"
                                            />
                                        </div>
                                        <div className="pattern-cue-sublabel">
                                            {getStrokeTipLabel(patternLayout.stroke.tip)} ({Math.round(getStrokeTipOffset(patternLayout.stroke)[0] * 100)}, {Math.round(getStrokeTipOffset(patternLayout.stroke)[1] * 100)})
                                        </div>
                                    </div>

                                    {/* 右側：力量進度條 */}
                                    <div className="pattern-power-wrap">
                                        <div className="pattern-cue-label">擊球力量</div>
                                        <div className="power-slider-shell">
                                            <input
                                                className="power-slider"
                                                type="range"
                                                min="1"
                                                max="100"
                                                step="1"
                                                value={getStrokePowerPercent(patternLayout.stroke)}
                                                onChange={(event) => handlePatternPowerPercent(Number(event.target.value))}
                                                aria-label="擊球力量"
                                            />
                                            <div className="power-slider-fill" style={{ width: `${getStrokePowerPercent(patternLayout.stroke)}%` }} />
                                        </div>
                                        <div className="power-bar-labels">
                                            {strokePowerOrder.map((power) => (
                                                <button
                                                    key={power}
                                                    type="button"
                                                    className={`power-label-btn${patternLayout.stroke.power === power ? ' active' : ''}`}
                                                    onClick={() => handlePatternStrokeChange({ ...patternLayout.stroke, power, power_percent: strokePowerPercentFallback[power] })}
                                                >
                                                    {getStrokePowerLabel(power)}
                                                </button>
                                            ))}
                                        </div>
                                        <div className="power-current-label">
                                            {getStrokePowerPercent(patternLayout.stroke)}% / {getStrokePowerLabel(patternLayout.stroke.power)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="setup-actions">
                        {practiceStartError && (
                            <div className="practice-start-error">{practiceStartError}</div>
                        )}
                        <button className="btn-primary btn-large" onClick={() => handleStartPractice()} disabled={practiceStartLoading}>
                            開始練習
                        </button>
                        <button className="btn-secondary" onClick={() => handleStartPractice(true)} disabled={practiceStartLoading}>
                            跳過，匿名練習
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // 渲染練習畫面
    return (
        <div className="practice-page">
            <div className="practice-header-active">
                <div className="header-left">
                    <h1>{mode === 'single' ? '一般練習' : '球型練習'}</h1>
                    {playerName && <span className="player-badge">玩家: {playerName}</span>}
                    {!playerName && <span className="player-badge anonymous">匿名玩家</span>}
                    {mode === 'pattern' && (
                        <span className="pattern-badge">
                            {pattern === 'straight' ? '直線球' :
                                pattern === 'cut' ? '切球' :
                                    pattern === 'bank' ? '反彈球' : '組合球'}
                        </span>
                    )}
                </div>
                <div className="header-right">
                    <div className={`status-badge ${isActive ? 'active' : 'paused'}`}>
                        {isActive ? '練習中' : '已暫停'}
                    </div>
                    {isRecording && (
                        <div className="recording-indicator">
                            錄影中 [REC] {formatDuration(recordingDuration)}
                        </div>
                    )}
                </div>
            </div>

            <div className="practice-content">
                {/* 統計面板 */}
                <div className="stats-panel">
                    <h3>練習統計</h3>
                    <div className="practice-player-info">
                        <span>玩家資訊</span>
                        <strong>{playerName || '匿名玩家'}</strong>
                    </div>
                    <div className="stats-grid">
                        <div className="stat-card">
                            <div className="stat-info">
                                <span className="stat-label">嘗試次數</span>
                                <span className="stat-value">{stats.attempts}</span>
                            </div>
                        </div>
                        <div className="stat-card success">
                            <div className="stat-info">
                                <span className="stat-label">成功次數</span>
                                <span className="stat-value">{stats.successes}</span>
                            </div>
                        </div>
                        <div className="stat-card rate">
                            <div className="stat-info">
                                <span className="stat-label">成功率</span>
                                <span className="stat-value">{Math.round(stats.success_rate * 100)}%</span>
                            </div>
                        </div>
                    </div>
                    <div className="practice-guide-controls">
                        <div className="yolo-drawing-control" role="group" aria-label="標註顯示模式">
                            <span className="yolo-drawing-label">標註顯示模式</span>
                            {([
                                ['none', '無'],
                                ['tactical', '精簡'],
                                ['full', '完整']
                            ] as Array<[YoloDrawingMode, string]>).map(([value, label]) => (
                                <button
                                    key={value}
                                    type="button"
                                    className={`yolo-drawing-btn ${yoloDrawingMode === value ? 'active' : ''}`}
                                    onClick={() => applyYoloDrawingMode(value)}
                                    disabled={isApplyingYoloDrawing}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                        <label className="pattern-toggle">
                            <input
                                type="checkbox"
                                checked={patternGuideOptions.cue_laser_enabled}
                                onChange={(event) => handlePatternGuideToggle('cue_laser_enabled', event.target.checked)}
                            />
                            <span>球桿雷射指引線</span>
                        </label>
                        {mode === 'pattern' && (
                            <label className="pattern-toggle">
                                <input
                                    type="checkbox"
                                    checked={patternGuideOptions.ball_guides_enabled}
                                    onChange={(event) => handlePatternGuideToggle('ball_guides_enabled', event.target.checked)}
                                />
                                <span>母球子球指引線</span>
                            </label>
                        )}
                    </div>
                </div>

                {/* 實時影像區域 */}
                <div className="video-container">
                    <img
                        src={`${backendUrl}/burnin/camera1.mjpg?quality=low&client_id=practice-monitor`}
                        alt="Practice Stream"
                        className="practice-stream"
                    />
                    {renderPracticeMetadataOverlay()}
                    {mode === 'single' && (
                        <div className="stroke-floating">
                            <button
                                type="button"
                                className={`stroke-floating-button ${strokePanelOpen ? 'active' : ''}`}
                                onClick={() => setStrokePanelOpen((open) => !open)}
                                aria-label="開啟桿法調整"
                                title="桿法調整"
                            >
                                <span className="stroke-ball-icon">
                                    <span className="stroke-ball-dot" style={getTipDotStyle(strokeControl)} />
                                </span>
                            </button>

                            {strokePanelOpen && (
                                <div className="stroke-panel" role="dialog" aria-label="桿法調整">
                                    <div className="stroke-panel-header">
                                        <strong>桿法調整</strong>
                                        <div className="stroke-panel-header-actions">
                                            <span>{getStrokeTipLabel(strokeControl.tip)} / {getStrokePowerLabel(strokeControl.power)}</span>
                                            <button
                                                type="button"
                                                className="stroke-reset-button"
                                                onClick={handleResetSingleStroke}
                                                disabled={plannerLoading}
                                            >
                                                重置
                                            </button>
                                        </div>
                                    </div>

                                    <div
                                        ref={singleCueBallRef}
                                        className="stroke-cue-ball-large stroke-cue-ball-draggable"
                                        role="slider"
                                        tabIndex={0}
                                        aria-label="母球撞點"
                                        aria-valuetext={getStrokeTipLabel(strokeControl.tip)}
                                        onPointerDown={(event) => {
                                            event.currentTarget.setPointerCapture(event.pointerId);
                                            setDraggingSingleTip(true);
                                            updateSingleTipFromPointer(event);
                                        }}
                                        onPointerMove={(event) => {
                                            if (draggingSingleTip) updateSingleTipFromPointer(event);
                                        }}
                                        onPointerUp={(event) => {
                                            event.currentTarget.releasePointerCapture(event.pointerId);
                                            setDraggingSingleTip(false);
                                        }}
                                        onPointerCancel={() => setDraggingSingleTip(false)}
                                    >
                                        <span className="cue-cross horizontal" aria-hidden="true" />
                                        <span className="cue-cross vertical" aria-hidden="true" />
                                        <span className="cue-equator" aria-hidden="true" />
                                        <span className="cue-dot-indicator" style={getTipDotStyle(strokeControl)} />
                                    </div>

                                    <div className="stroke-cue-sublabel">
                                        {getStrokeTipLabel(strokeControl.tip)} ({Math.round(getStrokeTipOffset(strokeControl)[0] * 100)}, {Math.round(getStrokeTipOffset(strokeControl)[1] * 100)})
                                    </div>

                                    <div className="stroke-power-slider-block">
                                        <div className="power-slider-shell">
                                            <input
                                                className="power-slider"
                                                type="range"
                                                min="1"
                                                max="100"
                                                step="1"
                                                value={getStrokePowerPercent(strokeControl)}
                                                onChange={(event) => handleSinglePowerPercent(Number(event.target.value))}
                                                aria-label="擊球力量"
                                                disabled={plannerLoading}
                                            />
                                            <div className="power-slider-fill" style={{ width: `${getStrokePowerPercent(strokeControl)}%` }} />
                                        </div>
                                        <div className="power-bar-labels">
                                            {strokePowerOrder.map((power) => (
                                            <button
                                                key={power}
                                                type="button"
                                                className={`power-label-btn ${strokeControl.power === power ? 'active' : ''}`}
                                                onClick={() => handleApplyStroke({ ...strokeControl, power, power_percent: strokePowerPercentFallback[power] })}
                                                disabled={plannerLoading}
                                            >
                                                {getStrokePowerLabel(power)}
                                            </button>
                                            ))}
                                        </div>
                                        <div className="power-current-label">
                                            {getStrokePowerPercent(strokeControl)}% / {getStrokePowerLabel(strokeControl.power)}
                                        </div>
                                    </div>

                                    <p className="stroke-panel-note">
                                        調整後會重新預測母球擊後行徑與落點，並同步更新影像與 AR 線路。
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                    {!isActive && (
                        <div className="video-overlay">
                            <div className="overlay-message">
                                練習已暫停
                                <button className="btn-resume" onClick={() => setIsActive(true)}>
                                    繼續練習
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {mode === 'single' && (
                    <div className="practice-planner-panel">
                        <div className="practice-planner-header">
                            <h3>多球路徑規劃</h3>
                            <button
                                className="practice-planner-run"
                                onClick={() => handleRunPlanner()}
                                disabled={!isActive || plannerLoading}
                            >
                                {plannerLoading ? '規劃中...' : plannerPlan ? '重新規劃' : '啟動多球規劃'}
                            </button>
                        </div>

                        <label className="practice-planner-lookahead">
                            <input
                                type="checkbox"
                                checked={lookaheadEnabled}
                                onChange={(event) => handleLookaheadToggle(event.target.checked)}
                                disabled={plannerLoading}
                            />
                            <span>2-ply 走位預判</span>
                        </label>

                        {plannerError && <div className="practice-planner-error">{plannerError}</div>}

                        <div className="practice-planner-tabs">
                            <button
                                className={`practice-planner-tab ${plannerView === 'best' ? 'active' : ''}`}
                                onClick={() => setPlannerView('best')}
                            >
                                最佳
                            </button>
                            <button
                                className={`practice-planner-tab ${plannerView === 'topn' ? 'active' : ''}`}
                                onClick={() => setPlannerView('topn')}
                            >
                                Top-N
                            </button>
                            <button
                                className={`practice-planner-tab ${plannerView === 'coach' ? 'active' : ''}`}
                                onClick={() => setPlannerView('coach')}
                            >
                                教練
                            </button>
                        </div>

                        {!plannerPlan && !plannerError && (
                            <div className="practice-planner-empty">按下啟動後，系統會使用目前球桌狀態產生候選路線。</div>
                        )}

                        {plannerPlan && plannerView === 'best' && (
                            <div className="practice-planner-content">
                                {plannerPlan.best_route ? (
                                    <>
                                        <div className="practice-planner-best-grid">
                                            <div>
                                                <span>路線</span>
                                                <strong>{plannerPlan.best_route.route_type}</strong>
                                            </div>
                                            <div>
                                                <span>目標球</span>
                                                <strong>{getRouteBallLabel(plannerPlan.best_route)}</strong>
                                            </div>
                                            <div>
                                                <span>成功率</span>
                                                <strong>{(plannerPlan.best_route.success_prob * 100).toFixed(0)}%</strong>
                                            </div>
                                            <div>
                                                <span>難度</span>
                                                <strong>{plannerPlan.best_route.difficulty}</strong>
                                            </div>
                                            <div>
                                                <span>預計落點</span>
                                                <strong>
                                                    {plannerPlan.best_route.cue_landing_point
                                                        ? `${plannerPlan.best_route.cue_landing_point[0]}, ${plannerPlan.best_route.cue_landing_point[1]}`
                                                        : '-'}
                                                </strong>
                                            </div>
                                        </div>
                                        <div className="practice-planner-stroke">
                                            <span>{plannerPlan.best_route.stroke_hint.type}</span>
                                            <span>{plannerPlan.best_route.stroke_hint.power}</span>
                                            <span>{plannerPlan.best_route.stroke_hint.spin}</span>
                                        </div>
                                        {renderPositionPlaySummary(plannerPlan.best_route)}
                                        {renderLookaheadNextRoute(plannerPlan.best_route)}
                                        {plannerPlan.best_route.metadata?.physics && (
                                            <div className="practice-planner-physics">
                                                <span>母球速度 {Number((plannerPlan.best_route.metadata.physics as Record<string, unknown>).cue_speed_after ?? 0).toFixed(2)}</span>
                                                <span>子球速度 {Number((plannerPlan.best_route.metadata.physics as Record<string, unknown>).object_speed ?? 0).toFixed(2)}</span>
                                                <span>容錯 {Number((plannerPlan.best_route.metadata.physics as Record<string, unknown>).line_tolerance_px ?? 0).toFixed(1)}px</span>
                                            </div>
                                        )}
                                        <p className="practice-planner-note">{plannerPlan.best_route.stroke_hint.rationale}</p>
                                    </>
                                ) : (
                                    <div className="practice-planner-empty">{plannerPlan.error || '目前沒有可行路線。'}</div>
                                )}
                            </div>
                        )}

                        {plannerPlan && plannerView === 'topn' && (
                            <div className="practice-planner-route-list">
                                <div className="practice-planner-route-head">
                                    <span>#</span>
                                    <span>路線</span>
                                    <span>目標</span>
                                    <span>進球</span>
                                    <span>走位</span>
                                    <span>2-ply</span>
                                    <span>落點</span>
                                </div>
                                {plannerPlan.routes.map((route, index) => (
                                    <div className="practice-planner-route-item" key={route.id || index}>
                                        <button
                                            className={`practice-planner-route-row ${plannerPlan.best_route?.id === route.id ? 'active' : ''}`}
                                            onClick={() => handleSelectRoute(route)}
                                            disabled={plannerLoading}
                                        >
                                            <span>#{index + 1}</span>
                                            <strong>{getRouteDisplayName(route)}</strong>
                                            <span>Ball {getRouteBallLabel(route)}</span>
                                            <span>{(route.success_prob * 100).toFixed(0)}%</span>
                                            <span>
                                                走位 {route.position_play?.score?.position_success_prob != null
                                                    ? `${(route.position_play.score.position_success_prob * 100).toFixed(0)}%`
                                                    : '-'}
                                            </span>
                                            <span>
                                                {(() => {
                                                    const lookahead = getLookaheadSummary(route);
                                                    if (lookahead?.finalScore == null) return lookaheadEnabled ? '待重算' : '-';
                                                    return `${(lookahead.finalScore * 100).toFixed(0)}%`;
                                                })()}
                                            </span>
                                            <span>
                                                落點 {route.cue_landing_point ? `${route.cue_landing_point[0]},${route.cue_landing_point[1]}` : '-'}
                                            </span>
                                        </button>
                                        {renderLookaheadNextRoute(route, true)}
                                    </div>
                                ))}
                                {plannerPlan.routes.length < 2 && (
                                    <div className="practice-planner-empty">目前球型只產生一個高可信候選；系統會在 practice 模式補入可教學的替代路線。</div>
                                )}
                            </div>
                        )}

                        {plannerPlan && plannerView === 'coach' && (
                            <div className="practice-planner-coach-notes">
                                {(plannerPlan.coach_notes?.length ? plannerPlan.coach_notes : ['目前沒有教練提示。']).map((note, index) => (
                                    <p key={index}>{note}</p>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* 操作面板 */}
                <div className="action-panel">
                    <h3>記錄結果</h3>
                    <div className="action-buttons">
                        <button
                            className="btn-success"
                            onClick={() => handleRecordAttempt(true)}
                            disabled={!isActive}
                        >
                            <span className="btn-icon">成功</span>
                            <span className="btn-hint">Space</span>
                        </button>
                        <button
                            className="btn-danger"
                            onClick={() => handleRecordAttempt(false)}
                            disabled={!isActive}
                        >
                            <span className="btn-icon">失敗</span>
                            <span className="btn-hint">X</span>
                        </button>
                    </div>
                    <div className="action-controls">
                        <button
                            className="btn-control"
                            onClick={() => setIsActive(!isActive)}
                        >
                            {isActive ? '暫停' : '繼續'}
                        </button>
                        <button
                            className="btn-control end"
                            onClick={handleBackToMenu}
                        >
                            結束練習
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}







