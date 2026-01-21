/**
 * 玩家個人統計頁面
 * 
 * 顯示特定玩家的練習成功率和對戰統計
 */

import React, { useState, useEffect } from 'react';
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
                return '本週';
            case 'month':
                return '本月';
            case 'all':
                return '全部';
        }
    };

    return (
        <div className="stats-page">
            {/* 頁首 */}
            <div className="stats-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← 返回
                    </button>
                )}
                <h1>{playerName} 的統計分析</h1>
            </div>

            {/* 時間範圍選擇 */}
            <div className="time-range-selector">
                <span className="selector-label">時間範圍:</span>
                <button
                    className={`range-btn ${timeRange === 'week' ? 'active' : ''}`}
                    onClick={() => setTimeRange('week')}
                >
                    本週
                </button>
                <button
                    className={`range-btn ${timeRange === 'month' ? 'active' : ''}`}
                    onClick={() => setTimeRange('month')}
                >
                    本月
                </button>
                <button
                    className={`range-btn ${timeRange === 'all' ? 'active' : ''}`}
                    onClick={() => setTimeRange('all')}
                >
                    全部
                </button>
            </div>

            {loading ? (
                <div className="loading">載入中...</div>
            ) : (
                <>
                    {/* 個人對戰統計 */}
                    {playerStats && (
                        <div className="stats-section">
                            <h2>對戰統計 ({getTimeRangeLabel()})</h2>
                            <div className="stats-cards">
                                <div className="stat-card">
                                    <h3 className="stat-title">總局數</h3>
                                    <div className="stat-content">
                                        <div className="stat-value success-rate">
                                            {playerStats.total_games}
                                        </div>
                                    </div>
                                </div>
                                <div className="stat-card">
                                    <h3 className="stat-title">勝場</h3>
                                    <div className="stat-content">
                                        <div className="stat-value success-rate">
                                            {playerStats.total_wins}
                                        </div>
                                    </div>
                                </div>
                                <div className="stat-card">
                                    <h3 className="stat-title">勝率</h3>
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
                            <h2>練習記錄</h2>
                            <div className="stat-card">
                                <h3 className="stat-title">總練習次數</h3>
                                <div className="stat-content">
                                    <div className="stat-value success-rate">
                                        {playerStats.total_practice_sessions || 0}
                                    </div>
                                </div>
                            </div>

                            {playerStats.recent_practice && playerStats.recent_practice.length > 0 && (
                                <div className="recent-practice">
                                    <h3>最近練習</h3>
                                    <div className="practice-list">
                                        {playerStats.recent_practice.map((practice, index) => (
                                            <div key={index} className="practice-item">
                                                <span className="practice-type">{practice.practice_type}</span>
                                                <div className="practice-duration">
                                                    <span className="duration-label">練習時間:</span>
                                                    <span className="duration-value">
                                                        {Math.floor(practice.duration_seconds / 60)}:{String(Math.floor(practice.duration_seconds % 60)).padStart(2, '0')}
                                                    </span>
                                                </div>
                                                <span className="practice-date">
                                                    {new Date(practice.date).toLocaleDateString('zh-TW')}
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
                        <button className="export-btn" onClick={() => alert('匯出功能開發中')}>
                            匯出 CSV
                        </button>
                        <button className="export-btn" onClick={() => alert('匯出功能開發中')}>
                            匯出 JSON
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default StatsPage;
