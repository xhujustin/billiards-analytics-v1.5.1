/**
 * 玩家個人統計頁面
 * 
 * 顯示特定玩家的練習成功率和對戰統計
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
        <div className="stats-page">
            {/* 頁首 */}
            <div className="stats-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← {t('common.back')}
                    </button>
                )}
                <h1>{t('replay.statsTitle', { player: playerName })}</h1>
            </div>

            {/* 時間範圍選擇 */}
            <div className="time-range-selector">
                <span className="selector-label">{t('replay.timeRange')}:</span>
                <button
                    className={`range-btn ${timeRange === 'week' ? 'active' : ''}`}
                    onClick={() => setTimeRange('week')}
                >
                    {t('replay.week')}
                </button>
                <button
                    className={`range-btn ${timeRange === 'month' ? 'active' : ''}`}
                    onClick={() => setTimeRange('month')}
                >
                    {t('replay.month')}
                </button>
                <button
                    className={`range-btn ${timeRange === 'all' ? 'active' : ''}`}
                    onClick={() => setTimeRange('all')}
                >
                    {t('replay.all')}
                </button>
            </div>

            {loading ? (
                <div className="loading">{t('replay.loading')}</div>
            ) : (
                <>
                    {/* 個人對戰統計 */}
                    {playerStats && (
                        <div className="stats-section">
                            <h2>{t('replay.battleStats')} ({getTimeRangeLabel()})</h2>
                            <div className="stats-cards">
                                <div className="stat-card">
                                    <h3 className="stat-title">{t('replay.totalGames')}</h3>
                                    <div className="stat-content">
                                        <div className="stat-value success-rate">
                                            {playerStats.total_games}
                                        </div>
                                    </div>
                                </div>
                                <div className="stat-card">
                                    <h3 className="stat-title">{t('replay.wins')}</h3>
                                    <div className="stat-content">
                                        <div className="stat-value success-rate">
                                            {playerStats.total_wins}
                                        </div>
                                    </div>
                                </div>
                                <div className="stat-card">
                                    <h3 className="stat-title">{t('replay.winRate')}</h3>
                                    <div className="stat-content">
                                        <div className="stat-value success-rate">
                                            {(playerStats.win_rate * 100).toFixed(1)}%
                                        </div>
                                        <div className="progress-bar">
                                            <div
                                                className="progress-fill"
                                                style={{ width: `${playerStats.win_rate * 100}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 個人練習記錄 */}
                    {playerStats && playerStats.total_practice_sessions !== undefined && (
                        <div className="stats-section">
                            <h2>{t('replay.practiceRecords')}</h2>
                            <div className="stat-card">
                                <h3 className="stat-title">{t('replay.totalPractice')}</h3>
                                <div className="stat-content">
                                    <div className="stat-value success-rate">
                                        {playerStats.total_practice_sessions || 0}
                                    </div>
                                </div>
                            </div>

                            {playerStats.recent_practice && playerStats.recent_practice.length > 0 && (
                                <div className="recent-practice">
                                    <h3>{t('replay.recentPractice')}</h3>
                                    <div className="practice-list">
                                        {playerStats.recent_practice.map((practice, index) => (
                                            <div key={index} className="practice-item">
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
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}


                    {/* 匯出功能 */}
                    <div className="export-section">
                        <button className="export-btn" onClick={() => alert(t('replay.exportTodo'))}>
                            {t('replay.exportCsv')}
                        </button>
                        <button className="export-btn" onClick={() => alert(t('replay.exportTodo'))}>
                            {t('replay.exportJson')}
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default StatsPage;
