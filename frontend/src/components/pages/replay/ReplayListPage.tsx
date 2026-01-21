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
            // 獲取所有錄影（後端不支援查詢參數）
            const response = await fetch('/api/recordings');

            if (response.ok) {
                const data = await response.json();
                const allRecordings = data.recordings || [];

                // 根據模式過濾錄影
                const filtered = allRecordings.filter((rec: Recording) => {
                    if (mode === 'game') {
                        return rec.game_type === 'nine_ball';
                    } else {
                        // 練習模式：包含 practice_single 和 practice_pattern
                        return rec.game_type === 'practice_single' || rec.game_type === 'practice_pattern';
                    }
                });

                // 計算總頁數
                setTotalPages(Math.ceil(filtered.length / pageSize));

                // 客戶端分頁
                const startIndex = (currentPage - 1) * pageSize;
                const endIndex = startIndex + pageSize;
                const paginatedRecordings = filtered.slice(startIndex, endIndex);

                setRecordings(paginatedRecordings);
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

    const handleDeleteClick = async (gameId: string) => {
        // 確認刪除
        if (!window.confirm('確定要刪除這個錄影嗎？此操作無法復原。')) {
            return;
        }

        try {
            const response = await fetch(`/api/recordings/${gameId}`, {
                method: 'DELETE'
            });

            if (response.ok || response.status === 204) {
                // 刪除成功，重新載入列表
                alert('錄影已刪除');
                fetchRecordings();
            } else {
                const error = await response.json();
                alert(`刪除失敗: ${error.error?.message || '未知錯誤'}`);
            }
        } catch (error) {
            console.error('Failed to delete recording:', error);
            alert('刪除失敗，請稍後再試');
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
                                <img
                                    src={`/api/recordings/${recording.game_id}/thumbnail`}
                                    alt="錄影縮圖"
                                    onError={(e) => {
                                        // 如果縮圖加載失敗，顯示佔位符
                                        (e.target as HTMLImageElement).style.display = 'none';
                                        (e.target as HTMLImageElement).parentElement!.innerHTML = '<div class="thumbnail-placeholder">1280x720</div>';
                                    }}
                                />
                            </div>

                            <div className="recording-info">
                                <h3 className="recording-title">
                                    {mode === 'game'
                                        ? `${recording.player1_name} vs ${recording.player2_name}`
                                        : recording.game_type === 'practice_single' ? '單球練習' : '球型練習'
                                    }
                                </h3>

                                {mode === 'practice' && recording.player1_name && (
                                    <p className="recording-player">
                                        玩家: {recording.player1_name}
                                    </p>
                                )}

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
                                <button
                                    className="delete-button"
                                    onClick={() => handleDeleteClick(recording.game_id)}
                                    title="刪除錄影"
                                >
                                    刪除
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
