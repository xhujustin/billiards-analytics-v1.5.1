import { useState, useEffect, useRef } from 'react';
import type { PointerEvent } from 'react';
import './PracticePage.css';
import { PageType } from '../Sidebar';
import type { MetadataUpdatePayload, MultiRoutePlan, RouteCandidate } from '../../sdk/types';

type PracticeMode = 'menu' | 'player-setup' | 'single' | 'pattern';
type PracticePattern = 'straight' | 'cut' | 'bank' | 'combo';
type StrokeTip = 'center' | 'top' | 'draw' | 'left' | 'right';
type StrokePower = 'low' | 'medium' | 'medium_high' | 'high';
type PatternBallId = 'cue' | 'object' | 'object2';

interface StrokeControl {
    tip: StrokeTip;
    power: StrokePower;
}

interface PatternBall {
    id: PatternBallId;
    label: string;
    x: number;
    y: number;
    type: 'cue' | 'object' | 'object2';
    visible: boolean;
}

interface PatternRouteSegment {
    type: string;
    points: Array<[number, number]>;
}

interface PatternLayout {
    balls: PatternBall[];
    route_segments: PatternRouteSegment[];
    cue_landing_point: [number, number];
    stroke: StrokeControl;
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

const clamp01 = (value: number) => Math.max(0.04, Math.min(0.96, value));

const getPatternBalls = (practicePattern: PracticePattern): PatternBall[] => {
    const presets: Record<PracticePattern, PatternBall[]> = {
        straight: [
            { id: 'cue', label: '母球', x: 0.28, y: 0.5, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.56, y: 0.5, type: 'object', visible: true },
            { id: 'object2', label: '第二子球', x: 0.7, y: 0.5, type: 'object2', visible: false }
        ],
        cut: [
            { id: 'cue', label: '母球', x: 0.28, y: 0.64, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.56, y: 0.42, type: 'object', visible: true },
            { id: 'object2', label: '第二子球', x: 0.72, y: 0.42, type: 'object2', visible: false }
        ],
        bank: [
            { id: 'cue', label: '母球', x: 0.27, y: 0.55, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.58, y: 0.34, type: 'object', visible: true },
            { id: 'object2', label: '第二子球', x: 0.74, y: 0.34, type: 'object2', visible: false }
        ],
        combo: [
            { id: 'cue', label: '母球', x: 0.22, y: 0.56, type: 'cue', visible: true },
            { id: 'object', label: '子球', x: 0.5, y: 0.48, type: 'object', visible: true },
            { id: 'object2', label: '第二子球', x: 0.64, y: 0.43, type: 'object2', visible: true }
        ]
    };
    return presets[practicePattern].map((ball) => ({ ...ball }));
};

const normalizeVector = (dx: number, dy: number): [number, number] => {
    const length = Math.hypot(dx, dy) || 1;
    return [dx / length, dy / length];
};

const getCueLandingPoint = (
    contact: PatternBall,
    object: PatternBall,
    stroke: StrokeControl
): [number, number] => {
    const [ox, oy] = normalizeVector(object.x - contact.x, object.y - contact.y);
    const powerScale: Record<StrokePower, number> = {
        low: 0.1,
        medium: 0.16,
        medium_high: 0.23,
        high: 0.3
    };
    const distance = powerScale[stroke.power];

    if (stroke.tip === 'top') return [clamp01(object.x + ox * distance), clamp01(object.y + oy * distance)];
    if (stroke.tip === 'draw') return [clamp01(object.x - ox * distance), clamp01(object.y - oy * distance)];
    if (stroke.tip === 'left') return [clamp01(object.x - oy * distance), clamp01(object.y + ox * distance)];
    if (stroke.tip === 'right') return [clamp01(object.x + oy * distance), clamp01(object.y - ox * distance)];
    return [clamp01(object.x - oy * distance * 0.55), clamp01(object.y + ox * distance * 0.55)];
};

const buildPatternSegments = (
    practicePattern: PracticePattern,
    balls: PatternBall[],
    stroke: StrokeControl
): { segments: PatternRouteSegment[]; landing: [number, number] } => {
    const cue = balls.find((ball) => ball.id === 'cue') || balls[0];
    const object = balls.find((ball) => ball.id === 'object') || balls[1];
    const object2 = balls.find((ball) => ball.id === 'object2') || balls[2];
    const pocket: [number, number] = practicePattern === 'bank' ? [0.16, 0.08] : [0.94, practicePattern === 'straight' ? object.y : 0.12];
    const railPoint: [number, number] = [object.x + 0.15, 0.08];
    const landing = getCueLandingPoint(cue, object, stroke);
    const segments: PatternRouteSegment[] = [
        { type: 'cue_to_contact', points: [[cue.x, cue.y], [object.x, object.y]] }
    ];

    if (practicePattern === 'bank') {
        segments.push({ type: 'object_to_rail', points: [[object.x, object.y], railPoint] });
        segments.push({ type: 'object_to_pocket', points: [railPoint, pocket] });
    } else if (practicePattern === 'combo' && object2?.visible) {
        segments.push({ type: 'combo_transfer', points: [[object.x, object.y], [object2.x, object2.y]] });
        segments.push({ type: 'object_to_pocket', points: [[object2.x, object2.y], pocket] });
    } else {
        segments.push({ type: 'object_to_pocket', points: [[object.x, object.y], pocket] });
    }

    segments.push({ type: 'cue_after_contact', points: [[object.x, object.y], landing] });
    return { segments, landing };
};

const createPatternLayout = (practicePattern: PracticePattern, stroke: StrokeControl): PatternLayout => {
    const balls = getPatternBalls(practicePattern);
    const { segments, landing } = buildPatternSegments(practicePattern, balls, stroke);
    return { balls, route_segments: segments, cue_landing_point: landing, stroke };
};

export default function PracticePage({ onNavigate, metadata }: PracticePageProps) {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';
    const projectorBounds = { x: 80, y: 80, width: 1760, height: 920 };
    const [mode, setMode] = useState<PracticeMode>('menu');
    const [selectedPracticeType, setSelectedPracticeType] = useState<'single' | 'pattern' | null>(null);
    const [pattern, setPattern] = useState<PracticePattern>('straight');
    const [isActive, setIsActive] = useState(false);
    const [stats, setStats] = useState<PracticeStats>({ attempts: 0, successes: 0, success_rate: 0 });
    const [plannerView, setPlannerView] = useState<'best' | 'topn' | 'coach'>('best');
    const [plannerPlan, setPlannerPlan] = useState<MultiRoutePlan | null>(null);
    const [plannerLoading, setPlannerLoading] = useState(false);
    const [plannerError, setPlannerError] = useState('');
    const [strokePanelOpen, setStrokePanelOpen] = useState(false);
    const [strokeControl, setStrokeControl] = useState<StrokeControl>({ tip: 'center', power: 'medium' });
    const [patternLayout, setPatternLayout] = useState<PatternLayout>(() => createPatternLayout('straight', { tip: 'center', power: 'medium' }));
    const [draggingPatternBall, setDraggingPatternBall] = useState<PatternBallId | null>(null);
    const patternTableRef = useRef<HTMLDivElement | null>(null);

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
            right: '右塞'
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

    const getTipDotClass = (tip: StrokeTip) => {
        if (tip === 'top') return 'top';
        if (tip === 'draw') return 'draw';
        if (tip === 'left') return 'left';
        if (tip === 'right') return 'right';
        return 'center';
    };

    // 玩家相關狀態
    const [playerName, setPlayerName] = useState('');
    const [existingPlayers, setExistingPlayers] = useState<string[]>([]);

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
                    setExistingPlayers(players);
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
        const { segments, landing } = buildPatternSegments(pattern, balls, stroke);
        setPatternLayout({
            balls,
            route_segments: segments,
            cue_landing_point: landing,
            stroke
        });
    };

    const handlePatternPointerMove = (event: PointerEvent<HTMLDivElement>) => {
        if (!draggingPatternBall || !patternTableRef.current) return;
        const rect = patternTableRef.current.getBoundingClientRect();
        const x = clamp01((event.clientX - rect.left) / rect.width);
        const y = clamp01((event.clientY - rect.top) / rect.height);
        const nextBalls = patternLayout.balls.map((ball) =>
            ball.id === draggingPatternBall ? { ...ball, x, y } : ball
        );
        updatePatternLayout(nextBalls);
    };

    const handlePatternStrokeChange = (nextStroke: StrokeControl) => {
        updatePatternLayout(patternLayout.balls, nextStroke);
    };

    const toProjectorPoint = (point: [number, number]): [number, number] => [
        Math.round(projectorBounds.x + point[0] * projectorBounds.width),
        Math.round(projectorBounds.y + point[1] * projectorBounds.height)
    ];

    const buildPatternProjectionPayload = () => ({
        balls: patternLayout.balls
            .filter((ball) => ball.visible)
            .map((ball) => {
                const [x, y] = toProjectorPoint([ball.x, ball.y]);
                return {
                    x,
                    y,
                    r: 24,
                    type: ball.type,
                    label: ball.label
                };
            }),
        route_segments: patternLayout.route_segments.map((segment) => ({
            type: segment.type,
            points: segment.points.map(toProjectorPoint)
        })),
        cue_landing_point: toProjectorPoint(patternLayout.cue_landing_point),
        stroke: patternLayout.stroke
    });

    // 開始練習
    const handleStartPractice = async (skipPlayer: boolean = false) => {
        try {
            const finalPlayerName = skipPlayer ? '' : playerName;
            const practiceType = selectedPracticeType === 'single' ? 'practice_single' : 'practice_pattern';

            // 啟動練習
            const response = await fetch('/api/practice/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: selectedPracticeType,
                    pattern: selectedPracticeType === 'pattern' ? pattern : null,
                    player_name: finalPlayerName,
                    pattern_layout: selectedPracticeType === 'pattern' ? buildPatternProjectionPayload() : null
                })
            });

            if (response.ok) {
                // 啟動錄影
                try {
                    const recordingResponse = await fetch('/api/recording/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            game_type: practiceType,
                            players: finalPlayerName ? [finalPlayerName] : []
                        })
                    });

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
            }
        } catch (error) {
            console.error('Failed to start practice:', error);
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

                        {existingPlayers.length > 0 && (
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
                        )}

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

                                <div
                                    className="pattern-virtual-table"
                                    ref={patternTableRef}
                                    onPointerMove={handlePatternPointerMove}
                                    onPointerUp={() => setDraggingPatternBall(null)}
                                    onPointerLeave={() => setDraggingPatternBall(null)}
                                >
                                    <div className="pattern-table-rail top" />
                                    <div className="pattern-table-rail bottom" />
                                    <div className="pattern-table-rail left" />
                                    <div className="pattern-table-rail right" />
                                    {patternLayout.route_segments.map((segment, index) =>
                                        segment.points.slice(1).map((endPoint, pointIndex) => {
                                            const startPoint = segment.points[pointIndex];
                                            const dx = endPoint[0] - startPoint[0];
                                            const dy = endPoint[1] - startPoint[1];
                                            const length = Math.hypot(dx, dy) * 100;
                                            const angle = Math.atan2(dy, dx) * 180 / Math.PI;
                                            return (
                                                <div
                                                    key={`${segment.type}-${index}-${pointIndex}`}
                                                    className={`pattern-route-line ${segment.type}`}
                                                    style={{
                                                        left: `${startPoint[0] * 100}%`,
                                                        top: `${startPoint[1] * 100}%`,
                                                        width: `${length}%`,
                                                        transform: `rotate(${angle}deg)`
                                                    }}
                                                />
                                            );
                                        })
                                    )}
                                    <div
                                        className="pattern-landing-point"
                                        style={{
                                            left: `${patternLayout.cue_landing_point[0] * 100}%`,
                                            top: `${patternLayout.cue_landing_point[1] * 100}%`
                                        }}
                                        title="母球落點"
                                    />
                                    {patternLayout.balls.filter((ball) => ball.visible).map((ball) => (
                                        <button
                                            key={ball.id}
                                            type="button"
                                            className={`pattern-draggable-ball ${ball.type}`}
                                            style={{ left: `${ball.x * 100}%`, top: `${ball.y * 100}%` }}
                                            onPointerDown={(event) => {
                                                event.currentTarget.setPointerCapture(event.pointerId);
                                                setDraggingPatternBall(ball.id);
                                            }}
                                            onPointerUp={() => setDraggingPatternBall(null)}
                                            aria-label={`移動${ball.label}`}
                                            title={`移動${ball.label}`}
                                        >
                                            {ball.type === 'cue' ? '' : ball.type === 'object2' ? '2' : '1'}
                                        </button>
                                    ))}
                                </div>

                                <div className="pattern-control-grid">
                                    <div className="pattern-control-group">
                                        <span>母球桿法</span>
                                        <div className="pattern-control-buttons">
                                            {(['center', 'top', 'draw', 'left', 'right'] as StrokeTip[]).map((tip) => (
                                                <button
                                                    key={tip}
                                                    type="button"
                                                    className={patternLayout.stroke.tip === tip ? 'active' : ''}
                                                    onClick={() => handlePatternStrokeChange({ ...patternLayout.stroke, tip })}
                                                >
                                                    {getStrokeTipLabel(tip)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="pattern-control-group">
                                        <span>力量</span>
                                        <div className="pattern-control-buttons">
                                            {(['low', 'medium', 'medium_high', 'high'] as StrokePower[]).map((power) => (
                                                <button
                                                    key={power}
                                                    type="button"
                                                    className={patternLayout.stroke.power === power ? 'active' : ''}
                                                    onClick={() => handlePatternStrokeChange({ ...patternLayout.stroke, power })}
                                                >
                                                    {getStrokePowerLabel(power)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="setup-actions">
                        <button className="btn-primary btn-large" onClick={() => handleStartPractice()}>
                            開始練習
                        </button>
                        <button className="btn-secondary" onClick={() => handleStartPractice(true)}>
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
                </div>

                {/* 實時影像區域 */}
                <div className="video-container">
                    <img
                        src={`${backendUrl}/burnin/camera1.mjpg?quality=low`}
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
                                    <span className={`stroke-ball-dot ${getTipDotClass(strokeControl.tip)}`} />
                                </span>
                            </button>

                            {strokePanelOpen && (
                                <div className="stroke-panel" role="dialog" aria-label="桿法調整">
                                    <div className="stroke-panel-header">
                                        <strong>桿法調整</strong>
                                        <span>{getStrokeTipLabel(strokeControl.tip)} / {getStrokePowerLabel(strokeControl.power)}</span>
                                    </div>

                                    <div className="stroke-cue-ball-large" aria-hidden="true">
                                        <span className={`stroke-cue-dot ${getTipDotClass(strokeControl.tip)}`} />
                                    </div>

                                    <div className="stroke-choice-grid">
                                        {(['center', 'top', 'draw', 'left', 'right'] as StrokeTip[]).map((tip) => (
                                            <button
                                                key={tip}
                                                type="button"
                                                className={`stroke-choice ${strokeControl.tip === tip ? 'active' : ''}`}
                                                onClick={() => handleApplyStroke({ ...strokeControl, tip })}
                                                disabled={plannerLoading}
                                            >
                                                <span className="stroke-choice-dot-wrap">
                                                    <span className={`stroke-choice-dot ${getTipDotClass(tip)}`} />
                                                </span>
                                                {getStrokeTipLabel(tip)}
                                            </button>
                                        ))}
                                    </div>

                                    <div className="stroke-power-row">
                                        {(['low', 'medium', 'medium_high', 'high'] as StrokePower[]).map((power) => (
                                            <button
                                                key={power}
                                                type="button"
                                                className={`stroke-power ${strokeControl.power === power ? 'active' : ''}`}
                                                onClick={() => handleApplyStroke({ ...strokeControl, power })}
                                                disabled={plannerLoading}
                                            >
                                                {getStrokePowerLabel(power)}
                                            </button>
                                        ))}
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







