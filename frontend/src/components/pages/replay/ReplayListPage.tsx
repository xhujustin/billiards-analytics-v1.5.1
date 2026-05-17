/**
 * 回放列表頁面
 * 
 * 顯示錄影列表（遊玩模式或練習模式）
 * 支援搜尋、篩選、排序和分頁
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
    const { t, i18n } = useTranslation();
    const [recordings, setRecordings] = useState<Recording[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState<'date' | 'duration'>('date');
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    const pageSize = 6;

    useEffect(() => {
        setCurrentPage(1);
    }, [mode]);

    useEffect(() => {
        fetchRecordings();
    }, [mode, currentPage, sortBy]);

    const fetchRecordings = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                mode,
                limit: String(pageSize),
                offset: String((currentPage - 1) * pageSize),
            });

            const response = await fetch(`/api/recordings?${params.toString()}`);

            if (response.ok) {
                const data = await response.json();
                const pageRecordings: Recording[] = data.recordings || [];

                const sortedRecordings = [...pageRecordings].sort((a, b) => {
                    if (sortBy === 'duration') {
                        return (b.duration_seconds || 0) - (a.duration_seconds || 0);
                    }
                    return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
                });

                const total = Number(data.total || 0);
                setTotalPages(Math.max(1, Math.ceil(total / pageSize)));
                setRecordings(sortedRecordings);
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
        return date.toLocaleString(i18n.language, {
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
        if (!window.confirm(t('replay.deleteConfirm'))) {
            return;
        }

        try {
            const response = await fetch(`/api/recordings/${gameId}`, {
                method: 'DELETE'
            });

            if (response.ok || response.status === 204) {
                // 刪除成功，重新載入列表
                alert(t('replay.deleted'));
                fetchRecordings();
            } else {
                const error = await response.json();
                alert(`${t('replay.deleteFailed')}: ${error.error?.message || t('replay.unknownError')}`);
            }
        } catch (error) {
            console.error('Failed to delete recording:', error);
            alert(t('replay.deleteRetry'));
        }
    };

    return (
        <div className="replay-list-page">
            {/* 頁首 */}
            <div className="replay-list-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← {t('common.back')}
                    </button>
                )}
                <h1>{t('replay.listTitle', { mode: mode === 'game' ? t('replay.gameMode') : t('replay.practiceMode') })}</h1>
            </div>

            {/* 搜尋和篩選 */}
            <div className="replay-list-filters">
                <input
                    type="text"
                    className="search-input"
                    placeholder={t('replay.searchPlaceholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />

                <select
                    className="sort-select"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as 'date' | 'duration')}
                >
                    <option value="date">{t('replay.sortByDate')}</option>
                    <option value="duration">{t('replay.sortByDuration')}</option>
                </select>
            </div>

            {/* 錄影列表 */}
            {loading ? (
                <div className="loading">{t('replay.loading')}</div>
            ) : filteredRecordings.length === 0 ? (
                <div className="empty-state">
                    <p>{t('replay.emptyRecordings')}</p>
                </div>
            ) : (
                <div className="recordings-grid">
                    {filteredRecordings.map((recording) => (
                        <div key={recording.game_id} className="recording-card">
                            <div className="recording-thumbnail">
                                <img
                                    src={`/api/recordings/${recording.game_id}/thumbnail`}
                                    alt={t('replay.thumbnailAlt')}
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
                                        : recording.game_type === 'practice_single' ? t('replay.singlePractice') : t('replay.patternPractice')
                                    }
                                </h3>

                                {mode === 'practice' && recording.player1_name && (
                                    <p className="recording-player">
                                        {t('replay.player')}: {recording.player1_name}
                                    </p>
                                )}

                                {mode === 'game' && (
                                    <p className="recording-score">
                                        {t('replay.score')}: {recording.player1_score}-{recording.player2_score}
                                    </p>
                                )}

                                <p className="recording-duration">
                                    {t('replay.duration')}: {formatDuration(recording.duration_seconds)}
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
                                    {t('replay.play')}
                                </button>
                                <button
                                    className="delete-button"
                                    onClick={() => handleDeleteClick(recording.game_id)}
                                    title={t('replay.deleteTitle')}
                                >
                                    {t('replay.delete')}
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
                        {t('replay.prevPage')}
                    </button>

                    <span className="pagination-info">
                        {currentPage} / {totalPages}
                    </span>

                    <button
                        className="pagination-button"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage(currentPage + 1)}
                    >
                        {t('replay.nextPage')}
                    </button>
                </div>
            )}
        </div>
    );
};

export default ReplayListPage;

