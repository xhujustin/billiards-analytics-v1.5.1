/**
 * 回放列表頁面
 * 
 * 顯示錄影列表（遊玩模式或練習模式）
 * 支援搜尋、篩選、排序和分頁
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
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
    has_video?: boolean;
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
    const [totalRecordings, setTotalRecordings] = useState(0);

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
                    return getRecordingTime(b) - getRecordingTime(a);
                });

                const total = Number(data.total || 0);
                setTotalRecordings(total);
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

    const getRecordingTime = (recording: Recording): number => {
        const match = recording.game_id.match(/^game_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
        if (match) {
            const [, year, month, day, hour, minute, second] = match;
            return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)).getTime();
        }
        return new Date(recording.start_time.replace(/([+-]\d{2}:?\d{2}|Z)$/i, '')).getTime();
    };

    const formatDate = (recording: Recording): string => {
        const match = recording.game_id.match(/^game_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
        if (match) {
            const [, year, month, day, hour, minute] = match;
            return `${year}/${month}/${day} ${hour}:${minute}`;
        }

        const date = new Date(recording.start_time.replace(/([+-]\d{2}:?\d{2}|Z)$/i, ''));
        return date.toLocaleString(i18n.language, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const filteredRecordings = recordings.filter((rec) => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            rec.player1_name?.toLowerCase().includes(query) ||
            rec.player2_name?.toLowerCase().includes(query) ||
            rec.game_id.toLowerCase().includes(query)
        );
    });

    const totalDuration = filteredRecordings.reduce((sum, rec) => sum + (rec.duration_seconds || 0), 0);
    const latestRecording = [...filteredRecordings].sort(
        (a, b) => getRecordingTime(b) - getRecordingTime(a)
    )[0];
    const averageDuration = filteredRecordings.length > 0 ? totalDuration / filteredRecordings.length : 0;

    const getRecordingTitle = (recording: Recording) => {
        if (mode === 'game') {
            return `${recording.player1_name || '玩家1'} vs ${recording.player2_name || '玩家2'}`;
        }
        if (recording.game_type === 'practice_single') return t('replay.singlePractice');
        if (recording.game_type === 'practice_accuracy') return '準度訓練';
        return t('replay.patternPractice');
    };

    const getRecordingResult = (recording: Recording) => {
        if (mode === 'game') {
            const score = `${recording.player1_score ?? 0}-${recording.player2_score ?? 0}`;
            return recording.winner ? `${t('replay.winner')}: ${recording.winner} · ${score}` : `${t('replay.score')}: ${score}`;
        }
        return recording.player1_name ? `${t('replay.player')}: ${recording.player1_name}` : t('replay.practiceMode');
    };

    const handlePlayClick = (recording: Recording) => {
        if (onPlayRecording) {
            onPlayRecording(recording.game_id);
        } else {
            console.log(`Play recording: ${recording.game_id}`);
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
        <div className="replay-list-page friend-match-page">
            <div className="friend-match-panel replay-list-panel">
                {/* 頁首 */}
                <header className="friend-match-header replay-list-header">
                    {onBack && (
                        <button
                            type="button"
                            className="friend-back-button replay-back-button"
                            onClick={onBack}
                        >
                            ← <span className="replay-back-button-text">{t('common.back')}</span>
                        </button>
                    )}
                    <div>
                        <h1>{t('replay.listTitle', { mode: mode === 'game' ? t('replay.gameMode') : t('replay.practiceMode') })}</h1>
                        <p>{mode === 'game' ? '查看對戰錄影、比分結果與回放操作。' : '查看練習錄影、訓練類型與回放操作。'}</p>
                    </div>
                </header>

                <section className="friend-setup-section replay-list-overview">
                    <div className="friend-section-title">
                        <span>1</span>
                        <h2>統計概覽</h2>
                    </div>
                    <div className="friend-status-grid replay-summary-cards">
                        <div className="friend-status-pill replay-summary-card">
                            <span>{mode === 'game' ? '對戰記錄' : '練習記錄'}</span>
                            <strong>{totalRecordings}</strong>
                        </div>
                        <div className="friend-status-pill replay-summary-card">
                            <span>本頁平均時長</span>
                            <strong>{formatDuration(averageDuration)}</strong>
                        </div>
                        <div className="friend-status-pill replay-summary-card">
                            <span>最新記錄</span>
                            <strong>{latestRecording ? formatDate(latestRecording) : '--'}</strong>
                        </div>
                    </div>
                </section>

                {/* 搜尋和篩選 */}
                <section className="friend-setup-section replay-list-filters">
                    <div className="friend-section-title">
                        <span>2</span>
                        <h2>篩選與排序</h2>
                    </div>
                    <div className="replay-list-filter-row">
                        <input
                            type="text"
                            className="search-input replay-list-search"
                            placeholder={t('replay.searchPlaceholder')}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />

                        <select
                            className="sort-select replay-list-sort"
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value as 'date' | 'duration')}
                        >
                            <option value="date">{t('replay.sortByDate')}</option>
                            <option value="duration">{t('replay.sortByDuration')}</option>
                        </select>
                    </div>
                </section>

                {/* 錄影列表 */}
                <section className="friend-setup-section replay-list-content">
                    <div className="friend-section-title">
                        <span>3</span>
                        <h2>{t('replay.records')}</h2>
                    </div>

                    {loading ? (
                        <div className="loading">{t('replay.loading')}</div>
                    ) : filteredRecordings.length === 0 ? (
                        <div className="empty-state">
                            <p>{t('replay.emptyRecordings')}</p>
                        </div>
                    ) : (
                        <div className="recordings-list">
                            {filteredRecordings.map((recording) => (
                                <article key={recording.game_id} className="recording-card replay-recording-card">
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
                                            {getRecordingTitle(recording)}
                                        </h3>

                                        <div className="recording-meta-row">
                                            <span>{getRecordingResult(recording)}</span>
                                            <span>{t('replay.duration')}: {formatDuration(recording.duration_seconds)}</span>
                                            <span>{formatDate(recording)}</span>
                                            {recording.has_video === false && (
                                                <span className="recording-missing-video">影片檔遺失</span>
                                            )}
                                        </div>
                                    </div>

                                    <div className="recording-actions">
                                        <button
                                            className="play-button"
                                            onClick={() => handlePlayClick(recording)}
                                            title={recording.has_video === false ? '仍會嘗試播放；若失敗請確認 video.mp4 是否在 recordings 資料夾' : t('replay.play')}
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
                                </article>
                            ))}
                        </div>
                    )}
                </section>

                {/* 分頁 */}
                {totalPages > 1 && (
                    <div className="pagination">
                        <button
                            className="friend-start-button"
                            disabled={currentPage === 1}
                            onClick={() => setCurrentPage(currentPage - 1)}
                        >
                            {t('replay.prevPage')}
                        </button>

                        <span className="pagination-info">
                            {currentPage} / {totalPages}
                        </span>

                        <button
                            className="friend-start-button"
                            disabled={currentPage === totalPages}
                            onClick={() => setCurrentPage(currentPage + 1)}
                        >
                            {t('replay.nextPage')}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReplayListPage;
