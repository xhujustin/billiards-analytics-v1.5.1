import { useState, useEffect, useRef } from 'react';
import './PracticePage.css';
import { PageType } from '../Sidebar';
import type { MetadataUpdatePayload, MultiRoutePlan, RouteCandidate } from '../../sdk/types';

type PracticeMode = 'menu' | 'player-setup' | 'single' | 'pattern';
type PracticePattern = 'straight' | 'cut' | 'bank' | 'combo';

interface PracticeStats {
    attempts: number;
    successes: number;
    success_rate: number;
}

interface PracticePageProps {
    onNavigate: (page: PageType) => void;
    metadata?: MetadataUpdatePayload | null;
}

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

    const getRouteBallLabel = (route: RouteCandidate) => {
        const comboSecond = route.metadata?.combo_second_ball_number;
        if (route.route_type === 'combo' && typeof comboSecond === 'number') {
            return `${route.target_ball_number ?? '-'} → ${comboSecond}`;
        }
        return `${route.target_ball_number ?? '-'}`;
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
        setMode('player-setup');
    };

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
                    player_name: finalPlayerName
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
                    combo_depth: 2
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







