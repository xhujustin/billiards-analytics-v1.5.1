/**
 * 回放列表頁面
 * 
 * 顯示錄影列表（遊玩模式或練習模式）
 * 支援搜尋、篩選、排序和分頁
 */

import React, { useState, useEffect } from 'react';
import './ReplayListPage.css';

interface Recording {
    game_id: string;
    game_type: string;
    start_time: string;
    duration_seconds: number;
    player1_name?: string;
    player2_name?: string;
    player1_score?: number;
    player2_score?: number;
    winner?: string;
    video_resolution?: string;
    file_size_mb?: number;
}

interface ReplayListPageProps {
    mode: 'game' | 'practice';
    onBack?: () => void;
    onPlayRecording?: (gameId: string) => void;
}

const ReplayListPage: React.FC<ReplayListPageProps> = ({ mode, onBack, onPlayRecording }) => {
    const [recordings, setRecordings] = useState<Recording[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState<'date' | 'duration'>('date');
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    const pageSize = 6;

    useEffect(() => {
        fetchRecordings();
    }, [mode, currentPage, sortBy]);

    const fetchRecordings = async () => {
        setLoading(true);
        try {
            const gameType = mode === 'game' ? 'nine_ball' : 'practice_single,practice_pattern';
            const offset = (currentPage - 1) * pageSize;

            const response = await fetch(
                `/api/recordings?game_type=${gameType}&limit=${pageSize}&offset=${offset}`
            );

            if (response.ok) {
                const data = await response.json();
                setRecordings(data.recordings || []);
                setTotalPages(Math.ceil((data.total || 0) / pageSize));
            }
        } catch (error) {
            console.error('Failed to fetch recordings:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const formatDate = (dateString: string): string => {
        const date = new Date(dateString);
        return date.toLocaleString('zh-TW', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const filteredRecordings = recordings.filter(rec => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            rec.player1_name?.toLowerCase().includes(query) ||
            rec.player2_name?.toLowerCase().includes(query) ||
            rec.game_id.toLowerCase().includes(query)
        );
    });

    const handlePlayClick = (gameId: string) => {
        if (onPlayRecording) {
            onPlayRecording(gameId);
        } else {
            console.log(`Play recording: ${gameId}`);
        }
    };

    return (
        <div className="replay-list-page">
            {/* 頁首 */}
            <div className="replay-list-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← 返回
                    </button>
                )}
                <h1>{mode === 'game' ? '遊玩模式' : '練習模式'}回放記錄</h1>
            </div>

            {/* 搜尋和篩選 */}
            <div className="replay-list-filters">
                <input
                    type="text"
                    className="search-input"
                    placeholder="搜尋玩家或遊戲 ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />

                <select
                    className="sort-select"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as 'date' | 'duration')}
                >
                    <option value="date">依日期排序</option>
                    <option value="duration">依時長排序</option>
                </select>
            </div>

            {/* 錄影列表 */}
            {loading ? (
                <div className="loading">載入中...</div>
            ) : filteredRecordings.length === 0 ? (
                <div className="empty-state">
                    <p>目前沒有錄影記錄</p>
                </div>
            ) : (
                <div className="recordings-grid">
                    {filteredRecordings.map((recording) => (
                        <div key={recording.game_id} className="recording-card">
                            <div className="recording-thumbnail">
                                <div className="thumbnail-placeholder">
                                    {recording.video_resolution || '1280x720'}
                                </div>
                            </div>

                            <div className="recording-info">
                                <h3 className="recording-title">
                                    {mode === 'game'
                                        ? `${recording.player1_name} vs ${recording.player2_name}`
                                        : recording.game_type === 'practice_single' ? '單球練習' : '球型練習'
                                    }
                                </h3>

                                {mode === 'game' && (
                                    <p className="recording-score">
                                        比分: {recording.player1_score}-{recording.player2_score}
                                    </p>
                                )}

                                <p className="recording-duration">
                                    時長: {formatDuration(recording.duration_seconds)}
                                </p>

                                <p className="recording-date">
                                    {formatDate(recording.start_time)}
                                </p>
                            </div>

                            <div className="recording-actions">
                                <button
                                    className="play-button"
                                    onClick={() => handlePlayClick(recording.game_id)}
                                >
                                    播放
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* 分頁 */}
            {totalPages > 1 && (
                <div className="pagination">
                    <button
                        className="pagination-button"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage(currentPage - 1)}
                    >
                        上一頁
                    </button>

                    <span className="pagination-info">
                        {currentPage} / {totalPages}
                    </span>

                    <button
                        className="pagination-button"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage(currentPage + 1)}
                    >
                        下一頁
                    </button>
                </div>
            )}
        </div>
    );
};

export default ReplayListPage;
