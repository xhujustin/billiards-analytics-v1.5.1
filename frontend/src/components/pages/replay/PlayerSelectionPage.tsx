/**
 * 玩家選擇頁面
 * 
 * 顯示所有玩家列表，讓使用者選擇要查看統計的玩家
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
import './PlayerSelectionPage.css';

interface Player {
    name: string;
    total_games: number;
    total_wins: number;
    win_rate: number;
}

interface PlayerSelectionPageProps {
    onSelectPlayer: (playerName: string) => void;
}

const PlayerSelectionPage: React.FC<PlayerSelectionPageProps> = ({ onSelectPlayer }) => {
    const { t } = useTranslation();
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
        <div className="player-selection-page friend-match-page">
            <div className="friend-match-panel player-selection-panel">
                <header className="friend-match-header player-selection-header">
                    <div>
                        <h1>{t('replay.selectPlayer')}</h1>
                        <p>選擇玩家查看個人統計、勝率與歷史表現。</p>
                    </div>
                </header>

                <section className="friend-setup-section player-search-section">
                    <div className="friend-section-title">
                        <h2>玩家搜尋</h2>
                    </div>
                    <input
                        type="text"
                        className="search-input"
                        placeholder={t('replay.searchPlayerPlaceholder')}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </section>

                <section className="friend-setup-section player-list-section">
                    <div className="friend-section-title">
                        <h2>玩家列表</h2>
                    </div>

                    {loading ? (
                        <div className="loading">{t('replay.loading')}</div>
                    ) : filteredPlayers.length === 0 ? (
                        <div className="empty-state">
                            {searchQuery ? t('replay.noMatchingPlayer') : t('replay.noPlayerRecord')}
                        </div>
                    ) : (
                        <div className="players-grid">
                            {filteredPlayers.map((player, index) => (
                                <button
                                    key={index}
                                    type="button"
                                    className="friend-player-card ready player-card"
                                    onClick={() => onSelectPlayer(player.name)}
                                >
                                    <div className="friend-player-avatar host player-avatar">
                                        {player.name.charAt(0).toUpperCase()}
                                    </div>
                                    <div className="friend-player-info player-info">
                                        <div className="friend-player-title">
                                            <span>玩家</span>
                                            <b>統計</b>
                                        </div>
                                        <strong className="player-name">{player.name}</strong>
                                        <small>{t('replay.winRate')} {(player.win_rate * 100).toFixed(1)}%</small>
                                    </div>
                                    <div className="friend-status-grid player-stats-summary">
                                        <div className="friend-status-pill">
                                            <span>{t('replay.totalGames')}</span>
                                            <strong>{player.total_games}</strong>
                                        </div>
                                        <div className="friend-status-pill">
                                            <span>{t('replay.wins')}</span>
                                            <strong>{player.total_wins}</strong>
                                        </div>
                                        <div className="friend-status-pill">
                                            <span>{t('replay.winRate')}</span>
                                            <strong>{(player.win_rate * 100).toFixed(1)}%</strong>
                                        </div>
                                    </div>
                                    <div className="card-arrow">→</div>
                                </button>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
};

export default PlayerSelectionPage;
