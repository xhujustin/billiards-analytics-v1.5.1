import { useState, useEffect, useRef } from 'react';
import './GamePage.css';
import { PageType } from '../Sidebar';

type GameMode = 'menu' | 'setup' | 'legacySetup' | 'playing';
type GameType = 'nine_ball' | 'eight_ball' | 'ten_ball' | 'snooker';
type RoundSelection = '3' | '5' | '7' | 'custom';
type ShotTimeSelection = 'none' | '30' | '45' | '60' | 'custom';

interface GameState {
    mode: string;
    is_active: boolean;
    players: string[];
    current_player: number;
    scores: number[];
    target_rounds: number;
    target_ball: number;
    remaining_balls: number[];
    visual_remaining_balls?: number[];
    remaining_balls_source?: string;
    foul_detected: boolean;
    foul_reason: string | null;
    last_shot_result?: {
        first_contact: number | null;
        potted_balls: number[];
        cue_ball_potted: boolean;
        continue_turn: boolean;
        round_over: boolean;
        game_over: boolean;
        auto_applied: boolean;
    } | null;
    game_options: GameOptions;
    // ⭐ v1.5 計時器欄位
    shot_time_limit: number;
    remaining_time: number;
    delay_used: [boolean, boolean];
    game_start_time: number;
    game_duration: number;
}

interface GameOptions {
    auto_pot_detection: boolean;
    foul_detection: boolean;
    auto_scoring: boolean;
    target_ar_hint_enabled: boolean;
}

interface GamePageProps {
    onNavigate: (page: PageType) => void;
    signedInPlayerName?: string;
}

export default function GamePage({ onNavigate, signedInPlayerName = '' }: GamePageProps) {
    const [mode, setMode] = useState<GameMode>('setup');
    const [gameType, setGameType] = useState<GameType>('nine_ball');
    const player1 = signedInPlayerName.trim() || '玩家1';
    const [player2, setPlayer2] = useState('玩家2');
    const [targetRounds, setTargetRounds] = useState(5);
    const [customRounds, setCustomRounds] = useState('');
    const [shotTimeLimit, setShotTimeLimit] = useState(30);
    const [roundSelection, setRoundSelection] = useState<RoundSelection>('5');
    const [shotTimeSelection, setShotTimeSelection] = useState<ShotTimeSelection>('30');
    const [customShotTime, setCustomShotTime] = useState('30');
    const [isPlayerTwoJoined, setIsPlayerTwoJoined] = useState(false);
    const [friendMatchNotice, setFriendMatchNotice] = useState('');
    const [saveBattleRecord, setSaveBattleRecord] = useState(true);
    const [generatePostMatchReport, setGeneratePostMatchReport] = useState(true);
    const [gameOptions, setGameOptions] = useState<GameOptions>({
        auto_pot_detection: true,
        foul_detection: true,
        auto_scoring: true,
        target_ar_hint_enabled: true,
    });
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [isRecording, setIsRecording] = useState(false);
    const [gameId, setGameId] = useState<string | null>(null);

    // ⭐ v1.5 計時器狀態
    const [remainingTime, setRemainingTime] = useState(0);
    const [delayUsed, setDelayUsed] = useState<[boolean, boolean]>([false, false]);
    const [gameDuration, setGameDuration] = useState(0);

    // ⭐ 防止重複觸發結束回合 (使用 ref 確保同步更新)
    const isEndingTurnRef = useRef(false);

    // ⭐ 遊戲結束狀態
    const [gameOver, setGameOver] = useState(false);
    const [winner, setWinner] = useState<string>('');
    const [countdown, setCountdown] = useState(5);

    // 獲取遊戲狀態
    const fetchGameState = async () => {
        try {
            const response = await fetch('/api/game/state');
            if (response.ok) {
                const data = await response.json();
                if (data.active !== false) {
                    if (
                        data.shot_time_limit > 0 &&
                        gameState &&
                        data.current_player !== gameState.current_player
                    ) {
                        setRemainingTime(data.remaining_time || data.shot_time_limit);
                    }
                    if (Array.isArray(data.delay_used)) {
                        setDelayUsed(data.delay_used);
                    }
                    setGameState(data);
                    // ⭐ 移除計時器狀態更新,避免覆蓋本地倒數計時器
                    // 只在遊戲開始時更新一次 (在 handleStartGame 中處理)
                    // setRemainingTime, setDelayUsed 由本地計時器和延時按鈕管理
                }
            }
        } catch (error) {
            console.error('Failed to fetch game state:', error);
        }
    };

    // 開始遊戲
    const handleStartGame = async () => {
        try {
            // 先啟動遊戲 (⭐ 修正:不依賴錄影)
            const gameResponse = await fetch('/api/game/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: gameType,
                    player1,
                    player2,
                    target_rounds: customRounds ? parseInt(customRounds) : targetRounds,
                    shot_time_limit: shotTimeLimit,  // ⭐ v1.5 新增
                    game_options: gameOptions
                })
            });

            if (gameResponse.ok) {
                console.log('✅ Game started successfully');

                // ⭐ 獲取初始遊戲狀態並設置計時器
                const gameData = await gameResponse.json();
                if (gameData.shot_time_limit && gameData.shot_time_limit > 0) {
                    setRemainingTime(gameData.shot_time_limit);
                    setDelayUsed([false, false]);
                }

                // 嘗試啟動錄影 (可選)
                try {
                    const recordingResponse = await fetch('/api/recording/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            game_type: gameType,
                            players: [player1, player2]
                        })
                    });

                    if (recordingResponse.ok) {
                        const recordingData = await recordingResponse.json();
                        setGameId(recordingData.game_id);
                        setIsRecording(true);
                        console.log('✅ Recording started:', recordingData.game_id);
                    } else {
                        console.warn('⚠️ Recording failed, but game continues');
                    }
                } catch (recordingError) {
                    console.warn('⚠️ Recording error:', recordingError);
                }

                // 切換到遊戲模式
                setMode('playing');
                fetchGameState();
            } else {
                const errorData = await gameResponse.json();
                console.error('❌ Failed to start game:', errorData);

                // 顯示詳細錯誤訊息
                const errorMsg = errorData.error_message || errorData.message || '未知錯誤';
                alert(`遊戲啟動失敗: ${errorMsg}\n\n請確認:\n1. 後端是否正常運行\n2. 遊戲模式是否支援\n3. 查看瀏覽器 Console 獲取更多資訊`);
            }
        } catch (error) {
            console.error('❌ Failed to start game:', error);
            alert('遊戲啟動失敗,請檢查後端是否運行');
        }
    };

    // ⭐ v1.5 新增: 延時處理
    const handleDelay = async () => {
        if (!gameState) return;

        try {
            const response = await fetch('/api/game/timer/delay', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ player: gameState.current_player })
            });

            if (response.ok) {
                const data = await response.json();
                // ⭐ 直接在當前剩餘時間上加30秒
                setRemainingTime(prev => prev + 30);
                setDelayUsed(data.delay_used);  // 更新延時使用狀態
                console.log('⏰ +30 seconds delay applied');
            }
        } catch (error) {
            console.error('Failed to apply delay:', error);
        }
    };

    const handleGameOptionChange = async (key: keyof GameOptions, value: boolean) => {
        const nextOptions = { ...(gameState?.game_options || gameOptions), [key]: value };
        if (key === 'auto_pot_detection' || key === 'auto_scoring') {
            nextOptions.auto_pot_detection = value;
            nextOptions.auto_scoring = value;
        }
        setGameOptions(nextOptions);

        if (mode !== 'playing') return;

        try {
            const response = await fetch('/api/game/options', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game_options: nextOptions })
            });

            if (response.ok) {
                await fetchGameState();
            } else {
                console.error('Failed to update game options:', await response.text());
            }
        } catch (error) {
            console.error('Failed to update game options:', error);
        }
    };

    // 結束回合
    const handleEndTurn = async () => {
        // ⭐ 防抖：如果正在結束回合，直接返回 (同步檢查)
        if (isEndingTurnRef.current) {
            console.log('⚠️ Already ending turn, skipping...');
            return;
        }

        try {
            isEndingTurnRef.current = true;  // 同步設置標誌
            console.log('🔚 Ending turn...');

            const response = await fetch('/api/game/end_turn', { method: 'POST' });
            if (response.ok) {
                const newState = await response.json();
                console.log('✅ New state received:', newState);

                // ⭐ 強制更新所有相關狀態
                setGameState({ ...newState });

                // ⭐ 重置計時器為時間限制值
                if (newState.shot_time_limit && newState.shot_time_limit > 0) {
                    const resetTime = newState.shot_time_limit;
                    setRemainingTime(resetTime);
                    console.log(`⏱️ Timer reset to ${resetTime} seconds, current player: ${newState.current_player}`);
                }

                // 記錄事件
                if (isRecording) {
                    await fetch('/api/recording/event', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            event_type: 'turn_end',
                            data: {
                                old_player: gameState?.current_player,
                                new_player: newState.current_player
                            }
                        })
                    });
                }
            } else {
                console.error('❌ End turn failed:', await response.text());
            }
        } catch (error) {
            console.error('❌ Failed to end turn:', error);
        } finally {
            // ⭐ 同步重置標誌
            console.log('🔓 Resetting isEndingTurn flag (sync)');
            isEndingTurnRef.current = false;
        }
    };

    // ⭐ 認輸功能 - 給對手加1局並繼續遊戲
    const handleForfeit = async () => {
        if (!gameState) return;

        const currentPlayerName = gameState.players[gameState.current_player - 1];
        const opponentPlayer = gameState.current_player === 1 ? 2 : 1;
        const opponentName = gameState.players[opponentPlayer - 1];

        try {
            console.log(`🏳️ Player ${gameState.current_player} (${currentPlayerName}) forfeits this round`);

            // 調用後端 API 給對手加分
            const response = await fetch('/api/game/forfeit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    forfeit_player: gameState.current_player
                })
            });

            if (response.ok) {
                const newState = await response.json();
                setGameState({ ...newState });

                // 重置計時器
                if (newState.shot_time_limit && newState.shot_time_limit > 0) {
                    setRemainingTime(newState.shot_time_limit);
                }

                // 記錄事件
                if (isRecording) {
                    await fetch('/api/recording/event', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            event_type: 'forfeit',
                            data: {
                                forfeit_player: currentPlayerName,
                                winner: opponentName,
                                round: newState.scores[opponentPlayer - 1]
                            }
                        })
                    });
                }

                // 檢查是否遊戲結束
                if (newState.scores[opponentPlayer - 1] >= newState.target_rounds) {
                    // 停止錄影
                    if (isRecording) {
                        await fetch('/api/recording/stop', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                final_score: newState.scores,
                                winner: opponentName,
                                total_rounds: newState.scores.reduce((a: number, b: number) => a + b, 0)
                            })
                        });
                    }

                    await fetch('/api/game/end', { method: 'POST' });

                    // ⭐ 顯示遊戲結束覆蓋層
                    setWinner(opponentName);
                    setGameOver(true);
                    setCountdown(5);
                } else {
                    // 繼續比賽
                    console.log(`${opponentName} 獲得1分! 當前比分: ${newState.scores[0]}-${newState.scores[1]}`);
                }
            } else {
                const error = await response.json();
                alert(`認輸失敗: ${error.error_message || error.message || '未知錯誤'}`);
            }
        } catch (error) {
            console.error('❌ Failed to forfeit:', error);
            alert('認輸失敗,請重試');
        }
    };

    // 結束遊戲
    const handleEndGame = async () => {
        try {
            // 停止錄影
            if (isRecording && gameId) {
                // 根據分數判斷勝者
                let winner = 'Unknown';
                if (gameState && gameState.scores) {
                    if (gameState.scores[0] > gameState.scores[1]) {
                        winner = gameState.players[0];
                    } else if (gameState.scores[1] > gameState.scores[0]) {
                        winner = gameState.players[1];
                    } else {
                        // 平手時兩位玩家都算勝利
                        winner = `${gameState.players[0]},${gameState.players[1]}`;
                    }
                }

                await fetch('/api/recording/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        final_score: gameState?.scores || [0, 0],
                        winner: winner,
                        total_rounds: gameState?.scores.reduce((a, b) => a + b, 0) || 0
                    })
                });
            }

            // 結束遊戲
            await fetch('/api/game/end', { method: 'POST' });

            setMode('setup');
            setGameState(null);
            setIsRecording(false);
            setGameId(null);
        } catch (error) {
            console.error('Failed to end game:', error);
        }
    };

    // ⭐ v1.5 新增: 格式化時長 (HH:MM:SS)
    const formatDuration = (seconds: number): string => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    // 自訂局數處理
    const handleCustomRounds = (value: string) => {
        setCustomRounds(value);
        const num = parseInt(value);
        if (!isNaN(num) && num >= 1 && num <= 99) {
            setTargetRounds(num);
        }
    };

    const handleRoundSelection = (selection: RoundSelection) => {
        setRoundSelection(selection);
        if (selection === 'custom') {
            const fallbackRounds = customRounds || `${targetRounds}`;
            setCustomRounds(fallbackRounds);
            handleCustomRounds(fallbackRounds);
            return;
        }

        setCustomRounds('');
        setTargetRounds(Number(selection));
    };

    const handleShotTimeSelection = (selection: ShotTimeSelection) => {
        setShotTimeSelection(selection);
        if (selection === 'none') {
            setShotTimeLimit(0);
            return;
        }

        if (selection === 'custom') {
            const nextTimeLimit = Math.max(1, Number(customShotTime) || 30);
            setShotTimeLimit(nextTimeLimit);
            return;
        }

        setShotTimeLimit(Number(selection));
    };

    const handleCustomShotTime = (value: string) => {
        setCustomShotTime(value);
        if (shotTimeSelection === 'custom') {
            const nextTimeLimit = Math.max(1, Number(value) || 30);
            setShotTimeLimit(nextTimeLimit);
        }
    };

    const handleInviteFriend = (method: 'qr' | 'code') => {
        console.log('[CueVex] invite friend by:', method);
        setPlayer2('現場好友');
        setIsPlayerTwoJoined(true);
        setFriendMatchNotice(method === 'qr' ? '已透過 QR Code 邀請好友加入。' : '已透過好友代碼邀請好友加入。');
    };

    const handleCreateFriendMatch = async () => {
        if (!isPlayerTwoJoined) return;

        const friendMatchSettings = {
            players: [player1, player2],
            gameType,
            targetRounds,
            shotTimeLimit,
            options: {
                ...gameOptions,
                saveBattleRecord,
                generatePostMatchReport,
            },
        };
        console.log('[CueVex] friend match settings:', friendMatchSettings);
        setFriendMatchNotice('對戰建立成功，正在啟動原本對戰流程。');
        await handleStartGame();
    };

    const handleOpenFriendMatch = () => {
        setMode('legacySetup');
        console.log('[CueVex] open friend match setup');
    };

    void onNavigate;

    // 輪詢遊戲狀態，讓自動進球、犯規與計分能同步回前端。
    useEffect(() => {
        if (mode === 'playing') {
            const interval = setInterval(fetchGameState, 1000);
            return () => clearInterval(interval);
        }
    }, [mode, gameState?.current_player]);

    // ⭐ 新增: 遊戲時長本地計時器 (避免依賴後端)
    useEffect(() => {
        if (mode === 'playing' && gameState && gameState.game_start_time) {
            const timer = setInterval(() => {
                const elapsed = Math.floor((Date.now() / 1000) - gameState.game_start_time);
                setGameDuration(elapsed);
            }, 1000);
            return () => clearInterval(timer);
        }
    }, [mode, gameState?.game_start_time]);

    // ⭐ 新增: 剩餘時間本地倒數計時器
    useEffect(() => {
        if (mode === 'playing' && gameState && gameState.shot_time_limit > 0) {
            console.log(`🔄 Timer created for Player ${gameState.current_player}, limit: ${gameState.shot_time_limit}s`);
            let hasTriggeredTimeout = false;  // 本地標誌,避免重複觸發

            const timer = setInterval(() => {
                setRemainingTime(prev => {
                    const newTime = prev - 1;

                    // ⭐ 只在第一次到達0時觸發
                    if (newTime === 0 && !hasTriggeredTimeout) {
                        hasTriggeredTimeout = true;
                        console.log(`⏰ Time out for Player ${gameState.current_player}! Auto ending turn...`);
                        setTimeout(() => handleEndTurn(), 500);
                    }

                    return Math.max(0, newTime);
                });
            }, 1000);

            return () => {
                console.log(`🛑 Timer cleared for Player ${gameState.current_player}`);
                clearInterval(timer);
            };
        }
    }, [mode, gameState?.shot_time_limit, gameState?.current_player]);  // ⭐ 添加 current_player 依賴,換人時重置

    // ⭐ 遊戲結束倒計時和鍵盤監聽
    useEffect(() => {
        if (gameOver) {
            // 倒計時
            const timer = setInterval(() => {
                setCountdown(prev => {
                    if (prev <= 1) {
                        handleReturnToMenu();
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);

            // 鍵盤監聽
            const handleKeyPress = () => {
                handleReturnToMenu();
            };

            window.addEventListener('keydown', handleKeyPress);

            return () => {
                clearInterval(timer);
                window.removeEventListener('keydown', handleKeyPress);
            };
        }
    }, [gameOver]);

    // 返回選單
    const handleReturnToMenu = () => {
        setGameOver(false);
        setWinner('');
        setMode('setup');
        setGameState(null);
        setIsRecording(false);
        setGameId(null);
    };

    // 渲染遊玩模式首頁
    if (mode === 'setup') {
        return (
            <div className="game-page play-home-page">
                <div className="play-home-layout">
                    <main className="play-main">
                        <header className="play-page-heading">
                            <h1>遊玩模式</h1>
                            <p>建立好友對戰，開始正式紀錄與自動判定流程</p>
                        </header>

                        <section className="play-mode-section" aria-labelledby="play-modes-title">
                            <div className="play-section-header">
                                <h2 id="play-modes-title">選擇遊玩模式</h2>
                            </div>

                            <div className="play-mode-grid">
                                <article className="play-mode-card">
                                    <div className="play-mode-card-top">
                                        <span className="play-mode-mark">2P</span>
                                        <h3>好友對戰</h3>
                                    </div>
                                    <p>與現場好友輪流擊球，系統自動記錄進球、犯規與比分。</p>
                                    <button
                                        type="button"
                                        className="play-secondary-button"
                                        onClick={handleOpenFriendMatch}
                                    >
                                        建立對戰
                                    </button>
                                </article>
                            </div>
                        </section>
                    </main>
                </div>
            </div>
        );
    }

    // 好友對戰先沿用原本的遊戲設定流程。
    if (mode === 'legacySetup') {
        const playerCountStatus = isPlayerTwoJoined ? '2 / 2' : '1 / 2';
        const startDisabled = !isPlayerTwoJoined;

        return (
            <div className="game-page friend-match-page">
                <div className="friend-match-panel">
                    <header className="friend-match-header">
                        <button className="friend-back-button" type="button" onClick={() => setMode('setup')} aria-label="返回遊玩模式">
                            ←
                        </button>
                        <div>
                            <h1>建立好友對戰</h1>
                            <p>邀請現場好友加入，設定比賽規則後由 CueVex 自動判定與記錄。</p>
                        </div>
                    </header>

                    {friendMatchNotice && (
                        <div className="friend-match-notice" role="status">
                            {friendMatchNotice}
                        </div>
                    )}

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>1</span>
                            <h2>玩家資訊</h2>
                        </div>
                        <div className="friend-player-grid">
                            <article className="friend-player-card ready">
                                <div className="friend-player-avatar host">123</div>
                                <div className="friend-player-info">
                                    <div className="friend-player-title">
                                        <span>玩家 1</span>
                                        <b>房主</b>
                                    </div>
                                    <strong>@123</strong>
                                    <small>已就緒</small>
                                </div>
                            </article>

                            <article className={`friend-player-card ${isPlayerTwoJoined ? 'ready' : 'waiting'}`}>
                                <div className="friend-player-avatar guest">{isPlayerTwoJoined ? '好友' : '?'}</div>
                                <div className="friend-player-info">
                                    <div className="friend-player-title">
                                        <span>玩家 2</span>
                                        <b>{isPlayerTwoJoined ? '已加入' : '等待中'}</b>
                                    </div>
                                    <strong>{isPlayerTwoJoined ? player2 : '尚未加入'}</strong>
                                    <small>{isPlayerTwoJoined ? '已就緒' : '請邀請現場好友加入'}</small>
                                </div>
                                {!isPlayerTwoJoined && (
                                    <div className="friend-invite-box">
                                        <span>邀請現場好友加入</span>
                                        <div className="friend-invite-actions">
                                            <button type="button" onClick={() => handleInviteFriend('qr')}>
                                                掃描 QR Code
                                            </button>
                                            <button type="button" onClick={() => handleInviteFriend('code')}>
                                                輸入好友代碼
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </article>
                        </div>
                    </section>

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>2</span>
                            <h2>遊戲類型</h2>
                        </div>
                        <div className="friend-game-type-grid">
                            <button className="friend-game-type-card active" type="button" onClick={() => setGameType('nine_ball')}>
                                <span className="friend-ball-mark">9</span>
                                <strong>9球</strong>
                                <small>可選</small>
                            </button>
                            {[
                                ['8球', '8'],
                                ['10球', '10'],
                                ['斯諾克', 'S'],
                            ].map(([label, mark]) => (
                                <button className="friend-game-type-card disabled" type="button" disabled key={label}>
                                    <span className="friend-ball-mark locked">{mark}</span>
                                    <strong>{label}</strong>
                                    <small>即將推出</small>
                                </button>
                            ))}
                        </div>
                    </section>

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>3</span>
                            <h2>遊玩局數</h2>
                        </div>
                        <div className="friend-segment-row">
                            {[
                                ['3', '3局'],
                                ['5', '5局'],
                                ['7', '7局'],
                                ['custom', '自訂局數'],
                            ].map(([value, label]) => (
                                <button
                                    type="button"
                                    key={value}
                                    className={roundSelection === value ? 'active' : ''}
                                    onClick={() => handleRoundSelection(value as RoundSelection)}
                                >
                                    {label}
                                </button>
                            ))}
                            <label className={`friend-inline-input ${roundSelection === 'custom' ? 'enabled' : ''}`}>
                                <span>局數</span>
                                <input
                                    type="number"
                                    min="1"
                                    max="99"
                                    value={customRounds || `${targetRounds}`}
                                    onChange={(e) => handleCustomRounds(e.target.value)}
                                    disabled={roundSelection !== 'custom'}
                                />
                            </label>
                        </div>
                    </section>

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>4</span>
                            <h2>出手時間限制</h2>
                        </div>
                        <div className="friend-segment-row">
                            {[
                                ['none', '無限制'],
                                ['30', '每回合 30 秒'],
                                ['45', '每回合 45 秒'],
                                ['60', '每回合 60 秒'],
                                ['custom', '自訂'],
                            ].map(([value, label]) => (
                                <button
                                    type="button"
                                    key={value}
                                    className={shotTimeSelection === value ? 'active' : ''}
                                    onClick={() => handleShotTimeSelection(value as ShotTimeSelection)}
                                >
                                    {label}
                                </button>
                            ))}
                            <label className={`friend-inline-input ${shotTimeSelection === 'custom' ? 'enabled' : ''}`}>
                                <span>秒</span>
                                <input
                                    type="number"
                                    min="1"
                                    max="180"
                                    value={customShotTime}
                                    onChange={(e) => handleCustomShotTime(e.target.value)}
                                    disabled={shotTimeSelection !== 'custom'}
                                />
                            </label>
                        </div>
                    </section>

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>5</span>
                            <h2>自動判定與紀錄</h2>
                        </div>
                        <div className="friend-check-grid">
                            {[
                                {
                                    label: '自動進球計分',
                                    checked: gameOptions.auto_pot_detection,
                                    onChange: (checked: boolean) => handleGameOptionChange('auto_pot_detection', checked),
                                },
                                {
                                    label: '犯規偵測',
                                    checked: gameOptions.foul_detection,
                                    onChange: (checked: boolean) => handleGameOptionChange('foul_detection', checked),
                                },
                                {
                                    label: '合法擊球提示',
                                    checked: gameOptions.target_ar_hint_enabled,
                                    onChange: (checked: boolean) => handleGameOptionChange('target_ar_hint_enabled', checked),
                                },
                                {
                                    label: '自動儲存對戰紀錄',
                                    checked: saveBattleRecord,
                                    onChange: setSaveBattleRecord,
                                },
                                {
                                    label: '產生賽後分析報告',
                                    checked: generatePostMatchReport,
                                    onChange: setGeneratePostMatchReport,
                                },
                            ].map((item) => (
                                <label className="friend-check-item" key={item.label}>
                                    <input
                                        type="checkbox"
                                        checked={item.checked}
                                        onChange={(event) => item.onChange(event.target.checked)}
                                    />
                                    <span>{item.label}</span>
                                </label>
                            ))}
                        </div>
                    </section>

                    <section className="friend-setup-section">
                        <div className="friend-section-title">
                            <span>6</span>
                            <h2>開始前檢查</h2>
                        </div>
                        <div className="friend-status-grid">
                            {[
                                ['鏡頭狀態', '正常', 'ok'],
                                ['球桌校正', '已完成', 'ok'],
                                ['YOLO 偵測', '啟用中', 'ok'],
                                ['WebSocket', '已連線', 'ok'],
                                ['玩家人數', playerCountStatus, isPlayerTwoJoined ? 'ok' : 'warning'],
                            ].map(([label, value, status]) => (
                                <div className={`friend-status-pill ${status}`} key={label}>
                                    <span>{label}</span>
                                    <strong>{value}</strong>
                                </div>
                            ))}
                        </div>
                    </section>

                    <div className="friend-start-area">
                        <button
                            className="friend-start-button"
                            type="button"
                            disabled={startDisabled}
                            onClick={handleCreateFriendMatch}
                        >
                            開始對戰
                        </button>
                        {startDisabled && <p>請先邀請好友加入（需 2 位玩家）</p>}
                    </div>
                </div>
            </div>
        );
    }

    // 渲染遊戲畫面
    return (
        <div className="game-page">
            {/* ⭐ v1.5 更新: 頂部欄包含計時器和時長 */}
            <div className="game-header-playing">
                <h1>{gameType === 'nine_ball' ? '9球對戰' : '遊戲對戰'}</h1>

                {/* 計時器區域 (只在有時間限制時顯示) */}
                {gameState && gameState.shot_time_limit > 0 && (
                    <div className="timer-section">
                        <div className={`timer ${remainingTime <= 10 ? 'warning' : ''} ${remainingTime <= 5 ? 'danger' : ''}`}>
                            剩餘 {remainingTime} 秒
                        </div>
                        <button
                            className="delay-btn"
                            disabled={gameState && delayUsed[gameState.current_player - 1]}
                            onClick={handleDelay}
                        >
                            {gameState && delayUsed[gameState.current_player - 1] ? '已用延時' : '+延時'}
                        </button>
                    </div>
                )}

                {/* 如果沒有時間限制,顯示佔位 */}
                {(!gameState || gameState.shot_time_limit === 0) && (
                    <div className="timer-section">
                        <div className="timer-placeholder">無時間限制</div>
                    </div>
                )}

                {/* 錄影和時長 (右上) */}
                <div className="recording-section">
                    {isRecording && (
                        <span className="recording-indicator">
                            錄影中 ({formatDuration(gameDuration)})
                        </span>
                    )}
                </div>
            </div>

            <div className="game-content">
                {/* ⭐ 調整順序: 比分在上 */}
                {gameState && (
                    <section className="score-section game-live-section">
                        <div className="friend-section-title">
                            <h2>比分</h2>
                        </div>
                        <div className="score-grid">
                            <div className={`player-score ${gameState.current_player === 1 ? 'active' : ''}`}>
                                <span className="player-name">{gameState.players[0]}</span>
                                <span className="score">{gameState.scores[0]}</span>
                                {gameState.current_player === 1 && <span className="current-indicator">當前</span>}
                            </div>

                            <div className="target-rounds">
                                <span className="target-text">先到</span>
                                <span className="target-number">{gameState.target_rounds}</span>
                                <span className="target-text">局獲勝</span>
                            </div>

                            <div className={`player-score ${gameState.current_player === 2 ? 'active' : ''}`}>
                                <span className="player-name">{gameState.players[1]}</span>
                                <span className="score">{gameState.scores[1]}</span>
                                {gameState.current_player === 2 && <span className="current-indicator">當前</span>}
                            </div>
                        </div>
                    </section>
                )}

                {/* 實時影像 */}
                <div className="video-container">
                    <img
                        src="/burnin/camera1.mjpg?quality=med&client_id=game-monitor"
                        alt="Game Stream"
                        className="game-stream"
                    />
                </div>

                {/* 遊戲狀態 */}
                {gameState && gameType === 'nine_ball' && (
                    <section className="game-status game-live-section">
                        <div className="friend-section-title">
                            <h2>遊戲狀態</h2>
                        </div>
                        <div className="status-info">
                            <div className="status-item">
                                <span>目標球:</span>
                                <span className="highlight">#{gameState.target_ball}</span>
                            </div>
                            <div className="status-item">
                                <span>剩餘球:</span>
                                <span className="balls-indicator">
                                    {gameState.remaining_balls.map(n => `①②③④⑤⑥⑦⑧⑨`[n - 1]).join('')}
                                </span>
                            </div>
                            <div className="status-item">
                                <span>剩餘球來源:</span>
                                <span>{gameState.remaining_balls_source === 'vision' ? '視覺修正' : gameState.remaining_balls_source === 'rules+vision' ? '規則+視覺' : '規則'}</span>
                            </div>
                            <div className="status-item">
                                <span>自動判定:</span>
                                <span>{gameState.game_options.auto_pot_detection ? '進球/計分開啟' : '進球/計分關閉'}</span>
                            </div>
                            <div className="status-item">
                                <span>犯規檢測:</span>
                                <span>{gameState.game_options.foul_detection ? '開啟' : '關閉'}</span>
                            </div>
                            <div className="status-item">
                                <span>AR 提示:</span>
                                <span>{gameState.game_options.target_ar_hint_enabled ? `提示 #${gameState.target_ball}` : '關閉'}</span>
                            </div>
                            {gameState.last_shot_result?.auto_applied && (
                                <div className="status-item">
                                    <span>上一桿:</span>
                                    <span>
                                        先碰 #{gameState.last_shot_result.first_contact ?? '-'}，進球 {gameState.last_shot_result.potted_balls.length > 0 ? gameState.last_shot_result.potted_balls.map(n => `#${n}`).join(', ') : '無'}
                                    </span>
                                </div>
                            )}
                        </div>
                    </section>
                )}

                {gameState && (
                    <section className="game-options-panel game-live-section">
                        <label className="option-switch compact">
                            <input
                                type="checkbox"
                                checked={gameState.game_options.auto_pot_detection}
                                onChange={(e) => handleGameOptionChange('auto_pot_detection', e.target.checked)}
                            />
                            <span>自動進球/計分</span>
                        </label>
                        <label className="option-switch compact">
                            <input
                                type="checkbox"
                                checked={gameState.game_options.foul_detection}
                                onChange={(e) => handleGameOptionChange('foul_detection', e.target.checked)}
                            />
                            <span>犯規檢測</span>
                        </label>
                        <label className="option-switch compact">
                            <input
                                type="checkbox"
                                checked={gameState.game_options.target_ar_hint_enabled}
                                onChange={(e) => handleGameOptionChange('target_ar_hint_enabled', e.target.checked)}
                            />
                            <span>AR 提示</span>
                        </label>
                    </section>
                )}

                {/* 犯規檢測 */}
                {gameState?.foul_detected && (
                    <div className="foul-alert">
                        犯規: {gameState.foul_reason}
                    </div>
                )}

                {/* 遊戲控制 */}
                <section className="game-actions game-live-section">
                    <button className="btn-secondary" onClick={handleEndTurn}>
                        結束回合
                    </button>
                    <button className="btn-danger" onClick={handleForfeit}>
                        認輸此回合
                    </button>
                    <button className="btn-warning" onClick={handleEndGame}>
                        結束遊戲
                    </button>
                </section>
            </div>

            {/* ⭐ 遊戲結束覆蓋層 */}
            {gameOver && (
                <div className="game-over-overlay">
                    <div className="game-over-content">
                        <h1 className="winner-text">{winner} 獲勝!</h1>
                        <p className="return-hint">按下任意鍵返回選單 ({countdown}秒)</p>
                    </div>
                </div>
            )}
        </div>
    );
}
