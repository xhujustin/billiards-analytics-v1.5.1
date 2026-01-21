import { useState, useEffect } from 'react';
import './PracticePage.css';
import { PageType } from '../Sidebar';

type PracticeMode = 'menu' | 'player-setup' | 'single' | 'pattern';
type PracticePattern = 'straight' | 'cut' | 'bank' | 'combo';

interface PracticeStats {
    attempts: number;
    successes: number;
    success_rate: number;
}

interface PracticePageProps {
    onNavigate: (page: PageType) => void;
}

export default function PracticePage({ onNavigate }: PracticePageProps) {
    const [mode, setMode] = useState<PracticeMode>('menu');
    const [selectedPracticeType, setSelectedPracticeType] = useState<'single' | 'pattern' | null>(null);
    const [pattern, setPattern] = useState<PracticePattern>('straight');
    const [isActive, setIsActive] = useState(false);
    const [stats, setStats] = useState<PracticeStats>({ attempts: 0, successes: 0, success_rate: 0 });

    // 玩家相關狀態
    const [playerName, setPlayerName] = useState('');
    const [existingPlayers, setExistingPlayers] = useState<string[]>([]);

    // 錄影相關狀態
    const [isRecording, setIsRecording] = useState(false);
    const [gameId, setGameId] = useState<string | null>(null);
    const [recordingDuration, setRecordingDuration] = useState(0);

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

    // 結束練習
    const handleEndPractice = async () => {
        try {
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
                        <h2>單球練習</h2>
                        <p className="card-description">專注於基本技巧，適合新手建立基礎</p>
                        <div className="card-badge">推薦初學者</div>
                    </div>

                    <div className="practice-card" onClick={() => handleSelectPracticeType('pattern')}>
                        <div className="card-icon">型</div>
                        <h2>球型練習</h2>
                        <p className="card-description">訓練特定球型，提升進階技術</p>
                        <div className="card-badge">適合進階</div>
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
                    <h1>練習模式 - {selectedPracticeType === 'single' ? '單球練習' : '球型練習'}</h1>
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
                            <h2>球型選擇</h2>
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
                                    disabled
                                >
                                    組合球(預留)
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
                    <h1>{mode === 'single' ? '單球練習' : '球型練習'}</h1>
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
                        src="/burnin/camera1.mjpg?quality=med"
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
