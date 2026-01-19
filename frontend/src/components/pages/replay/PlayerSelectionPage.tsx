/**
 * 玩家選擇頁面
 * 
 * 顯示所有玩家列表，讓使用者選擇要查看統計的玩家
 */

import React, { useState, useEffect } from 'react';
import './PlayerSelectionPage.css';

interface Player {
    name: string;
    total_games: number;
    total_wins: number;
    win_rate: number;
}

interface PlayerSelectionPageProps {
    onSelectPlayer: (playerName: string) => void;
    onBack?: () => void;
}

const PlayerSelectionPage: React.FC<PlayerSelectionPageProps> = ({ onSelectPlayer, onBack }) => {
    const [players, setPlayers] = useState<Player[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        fetchPlayers();
    }, []);

    const fetchPlayers = async () => {
        setLoading(true);
        try {
            const response = await fetch('/api/stats/summary');
            if (response.ok) {
                const data = await response.json();
                if (data.player_rankings) {
                    setPlayers(data.player_rankings);
                }
            }
        } catch (error) {
            console.error('Failed to fetch players:', error);
        } finally {
            setLoading(false);
        }
    };

    const filteredPlayers = players.filter(player =>
        player.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="player-selection-page">
            {/* 頁首 */}
            <div className="selection-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← 返回
                    </button>
                )}
                <h1>選擇玩家</h1>
            </div>

            {/* 搜尋框 */}
            <div className="search-section">
                <input
                    type="text"
                    className="search-input"
                    placeholder="搜尋玩家名稱..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

            {loading ? (
                <div className="loading">載入中...</div>
            ) : filteredPlayers.length === 0 ? (
                <div className="empty-state">
                    {searchQuery ? '找不到符合的玩家' : '目前沒有玩家記錄'}
                </div>
            ) : (
                <div className="players-grid">
                    {filteredPlayers.map((player, index) => (
                        <div
                            key={index}
                            className="player-card"
                            onClick={() => onSelectPlayer(player.name)}
                        >
                            <div className="player-avatar">
                                {player.name.charAt(0).toUpperCase()}
                            </div>
                            <div className="player-info">
                                <h3 className="player-name">{player.name}</h3>
                                <div className="player-stats-summary">
                                    <div className="stat-item">
                                        <span className="stat-label">總局數:</span>
                                        <span className="stat-value">{player.total_games}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-label">勝場:</span>
                                        <span className="stat-value">{player.total_wins}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-label">勝率:</span>
                                        <span className="stat-value win-rate">
                                            {(player.win_rate * 100).toFixed(1)}%
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="card-arrow">→</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default PlayerSelectionPage;
