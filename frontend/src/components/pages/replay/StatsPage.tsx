/**
 * 玩家個人統計頁面
 * 
 * 顯示特定玩家的練習成功率和對戰統計
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
import './StatsPage.css';


interface PlayerDetailStats {
    name: string;
    total_games: number;
    total_wins: number;
    win_rate: number;
    recent_games?: any[];
    total_practice_sessions?: number;
    recent_practice?: Array<{
        game_id: string;
        practice_type: string;
        duration_seconds: number;
        date: string;
    }>;
}

interface StatsPageProps {
    playerName: string;
    onBack?: () => void;
}

const StatsPage: React.FC<StatsPageProps> = ({ playerName, onBack }) => {
    const { t, i18n } = useTranslation();
    const [playerStats, setPlayerStats] = useState<PlayerDetailStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [timeRange, setTimeRange] = useState<'week' | 'month' | 'all'>('week');

    useEffect(() => {
        fetchStats();
    }, [timeRange, playerName]);

    const fetchStats = async () => {
        setLoading(true);
        try {
            // 獲取特定玩家的統計
            const playerResponse = await fetch(`/api/stats/player/${encodeURIComponent(playerName)}`);
            if (playerResponse.ok) {
                const data = await playerResponse.json();
                setPlayerStats(data);
            }
        } catch (error) {
            console.error('Failed to fetch stats:', error);
        } finally {
            setLoading(false);
        }
    };

    const getTimeRangeLabel = () => {
        switch (timeRange) {
            case 'week':
                return t('replay.week');
            case 'month':
                return t('replay.month');
            case 'all':
                return t('replay.all');
        }
    };

    return (
        <div className="stats-page friend-match-page">
            <div className="friend-match-panel stats-panel">
                <header className="friend-match-header stats-header">
                    {onBack && (
                        <button className="friend-back-button" type="button" onClick={onBack} aria-label={t('common.back')}>
                            ←
                        </button>
                    )}
                    <div>
                        <h1>{t('replay.statsTitle', { player: playerName })}</h1>
                        <p>查看個人對戰統計、練習紀錄與匯出資料。</p>
                    </div>
                </header>

            {/* 時間範圍選擇 */}
            <section className="friend-setup-section time-range-selector">
                <div className="friend-section-title">
                    <span>1</span>
                    <h2>{t('replay.timeRange')}</h2>
                </div>
                <div className="friend-segment-row stats-range-row">
                    <button
                        type="button"
                        className={timeRange === 'week' ? 'active' : ''}
                        onClick={() => setTimeRange('week')}
                    >
                        {t('replay.week')}
                    </button>
                    <button
                        type="button"
                        className={timeRange === 'month' ? 'active' : ''}
                        onClick={() => setTimeRange('month')}
                    >
                        {t('replay.month')}
                    </button>
                    <button
                        type="button"
                        className={timeRange === 'all' ? 'active' : ''}
                        onClick={() => setTimeRange('all')}
                    >
                        {t('replay.all')}
                    </button>
                </div>
            </section>

            {loading ? (
                <div className="loading">{t('replay.loading')}</div>
            ) : (
                <>
                    {/* 個人對戰統計 */}
                    {playerStats && (
                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title">
                                <span>2</span>
                                <h2>{t('replay.battleStats')} ({getTimeRangeLabel()})</h2>
                            </div>
                            <div className="friend-status-grid stats-cards">
                                <div className="friend-status-pill stat-card">
                                    <span>{t('replay.totalGames')}</span>
                                    <strong>{playerStats.total_games}</strong>
                                </div>
                                <div className="friend-status-pill stat-card">
                                    <span>{t('replay.wins')}</span>
                                    <strong>{playerStats.total_wins}</strong>
                                </div>
                                <div className="friend-status-pill stat-card stat-card-progress">
                                    <span>{t('replay.winRate')}</span>
                                    <strong>{(playerStats.win_rate * 100).toFixed(1)}%</strong>
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{ width: `${playerStats.win_rate * 100}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* 個人練習記錄 */}
                    {playerStats && playerStats.total_practice_sessions !== undefined && (
                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title">
                                <span>3</span>
                                <h2>{t('replay.practiceRecords')}</h2>
                            </div>
                            <div className="friend-status-grid stats-cards practice-total-grid">
                                <div className="friend-status-pill stat-card">
                                    <span>{t('replay.totalPractice')}</span>
                                    <strong>{playerStats.total_practice_sessions || 0}</strong>
                                </div>
                            </div>

                            {playerStats.recent_practice && playerStats.recent_practice.length > 0 && (
                                <div className="recent-practice">
                                    <h3>{t('replay.recentPractice')}</h3>
                                    <div className="practice-list">
                                        {playerStats.recent_practice.map((practice, index) => (
                                            <article key={index} className="practice-item">
                                                <span className="practice-type">{practice.practice_type}</span>
                                                <div className="practice-duration">
                                                    <span className="duration-label">{t('replay.practiceDuration')}:</span>
                                                    <span className="duration-value">
                                                        {Math.floor(practice.duration_seconds / 60)}:{String(Math.floor(practice.duration_seconds % 60)).padStart(2, '0')}
                                                    </span>
                                                </div>
                                                <span className="practice-date">
                                                    {new Date(practice.date).toLocaleDateString(i18n.language)}
                                                </span>
                                            </article>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </section>
                    )}


                    {/* 匯出功能 */}
                    <section className="friend-setup-section export-section">
                        <div className="friend-section-title">
                            <span>4</span>
                            <h2>{t('replay.exportCsv')}</h2>
                        </div>
                        <div className="friend-segment-row">
                            <button type="button" onClick={() => alert(t('replay.exportTodo'))}>
                                {t('replay.exportCsv')}
                            </button>
                            <button type="button" onClick={() => alert(t('replay.exportTodo'))}>
                                {t('replay.exportJson')}
                            </button>
                        </div>
                    </section>
                </>
            )}
            </div>
        </div>
    );
};

export default StatsPage;
