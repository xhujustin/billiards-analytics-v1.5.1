import { useState, useEffect, useRef } from 'react';
import type { PointerEvent } from 'react';
import './PracticePage.css';
import { PageType } from '../Sidebar';
import type { MetadataUpdatePayload, MultiRoutePlan, RouteCandidate } from '../../sdk/types';

type PracticeMode = 'menu' | 'player-setup' | 'single' | 'pattern';
type PracticePattern = 'straight' | 'cut' | 'bank' | 'combo';
type StrokeTip = 'center' | 'top' | 'draw' | 'left' | 'right' | 'top_left' | 'top_right' | 'draw_left' | 'draw_right';
type StrokePower = 'low' | 'medium' | 'medium_high' | 'high';
type PatternBallId = 'cue' | 'object' | 'object2';
type YoloDrawingMode = 'none' | 'tactical' | 'full';

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
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';
    const [mode, setMode] = useState<PracticeMode>('menu');
    const [selectedPracticeType, setSelectedPracticeType] = useState<'single' | 'pattern' | null>(null);
    const [pattern, setPattern] = useState<PracticePattern>('straight');
    const [isActive, setIsActive] = useState(false);
    const [stats, setStats] = useState<PracticeStats>({ attempts: 0, successes: 0, success_rate: 0 });
    const [plannerView, setPlannerView] = useState<'best' | 'topn' | 'coach'>('best');
    const [plannerPlan, setPlannerPlan] = useState<MultiRoutePlan | null>(null);
    const [plannerLoading, setPlannerLoading] = useState(false);
    const [plannerError, setPlannerError] = useState('');
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

    const getRouteBallLabel = (route: RouteCandidate) => {
        const comboSecond = route.metadata?.combo_second_ball_number;
        if (route.route_type === 'combo' && typeof comboSecond === 'number') {
            return `${route.target_ball_number ?? '-'} → ${comboSecond}`;
        }
        return `${route.target_ball_number ?? '-'}`;
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
            setPlannerPlan(metadata.multi_plan);
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

    const handleRunPlanner = async () => {
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
                    stroke: strokeControl
                })
            });

            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data?.error?.message || data?.message || '多球規劃啟動失敗');
            }

            setPlannerPlan(data.multi_plan);
        } catch (error) {
            const message = error instanceof Error ? error.message : '多球規劃啟動失敗';
            setPlannerError(message);
        } finally {
            setPlannerLoading(false);
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
                body: JSON.stringify({ stroke: nextStroke })
            });

            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data?.error?.message || data?.message || '桿法套用失敗');
            }

            setPlannerPlan(data.multi_plan);
        } catch (error) {
            const message = error instanceof Error ? error.message : '桿法套用失敗';
            setPlannerError(message);
        } finally {
            setPlannerLoading(false);
        }
    };

    const handleSelectRoute = async (route: RouteCandidate) => {
        if (!route.id) return;

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

            setPlannerPlan(data.multi_plan);
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
            setIsActive(false);
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
                    <h1>練習模式</h1>
                    <p>選擇練習類型，提升撞球技巧</p>
                </div>

                <div className="practice-menu">
                    <div className="practice-card" onClick={() => handleSelectPracticeType('single')}>
                        <div className="card-icon">球</div>
                        <h2>一般練習</h2>
                        <p className="card-description">自由擺球練習，支援多球路徑規劃與教練提示</p>
                        <div className="card-badge">含路徑規劃</div>
                    </div>

                    <div className="practice-card" onClick={() => handleSelectPracticeType('pattern')}>
                        <div className="card-icon">型</div>
                        <h2>球型練習</h2>
                        <p className="card-description">訓練直線、切球、反彈與組合球等固定球型</p>
                        <div className="card-badge">固定球型</div>
                    </div>
                </div>

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
                                onClick={handleRunPlanner}
                                disabled={!isActive || plannerLoading}
                            >
                                {plannerLoading ? '規劃中...' : plannerPlan ? '重新規劃' : '啟動多球規劃'}
                            </button>
                        </div>

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
                                {plannerPlan.routes.map((route, index) => (
                                    <button
                                        className={`practice-planner-route-row ${plannerPlan.best_route?.id === route.id ? 'active' : ''}`}
                                        key={route.id || index}
                                        onClick={() => handleSelectRoute(route)}
                                        disabled={plannerLoading}
                                    >
                                        <span>#{index + 1}</span>
                                        <strong>
                                            {typeof route.metadata?.strategy_label === 'string'
                                                ? route.metadata.strategy_label
                                                : route.route_type}
                                        </strong>
                                        <span>Ball {getRouteBallLabel(route)}</span>
                                        <span>{(route.success_prob * 100).toFixed(0)}%</span>
                                        <span>
                                            落點 {route.cue_landing_point ? `${route.cue_landing_point[0]},${route.cue_landing_point[1]}` : '-'}
                                        </span>
                                    </button>
                                ))}
                                <div className="practice-planner-empty">點選任一列可切換目前 AR/影像顯示的進球線路。</div>
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







