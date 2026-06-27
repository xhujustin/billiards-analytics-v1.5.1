/**
 * 回放播放器
 * 
 * 播放錄影影片（H.264 格式）
 * 顯示遊戲資訊和事件時間軸
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './ReplayPlayer.css';

interface Event {
    id: number;
    timestamp: number;
    offset_seconds?: number | null;
    event_type: string;
    data: any;
    source?: string;
}

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
    has_video?: boolean;
}

interface ReplayPlayerProps {
    gameId: string;
    onBack?: () => void;
}

const ReplayPlayer: React.FC<ReplayPlayerProps> = ({ gameId, onBack }) => {
    const { t, i18n } = useTranslation();
    const [recording, setRecording] = useState<Recording | null>(null);
    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);
    const [videoError, setVideoError] = useState(false);

    useEffect(() => {
        setVideoError(false);
        fetchRecording();
        fetchEvents();
    }, [gameId]);

    const fetchRecording = async () => {
        try {
            const response = await fetch(`/api/recordings/${gameId}`);
            if (response.ok) {
                const data = await response.json();
                setRecording(data);
            }
        } catch (error) {
            console.error('Failed to fetch recording:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchEvents = async () => {
        try {
            const response = await fetch(`/api/recordings/${gameId}/events`);
            if (response.ok) {
                const data = await response.json();
                setEvents(data.events || []);
            }
        } catch (error) {
            console.error('Failed to fetch events:', error);
        }
    };

    const formatDuration = (seconds: number): string => {
        const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
        const mins = Math.floor(safeSeconds / 60);
        const secs = Math.floor(safeSeconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getEventOffset = (event: Event): number => {
        if (typeof event.offset_seconds === 'number') {
            return event.offset_seconds;
        }

        return event.timestamp - new Date(recording?.start_time || '').getTime() / 1000;
    };

    const formatEventLabel = (event: Event): string => {
        if (event.event_type !== 'shot') {
            return event.event_type;
        }

        const shotIndex = event.data?.shot_index ? ` #${event.data.shot_index}` : '';
        const pottedBalls = Array.isArray(event.data?.potted_balls) ? event.data.potted_balls : [];
        const result = event.data?.is_foul
            ? '犯規'
            : event.data?.cue_ball_potted
                ? '母球洗袋'
                : pottedBalls.length > 0 || event.data?.pocket_result === 'made'
                    ? '進球'
                    : '未進';

        return `擊球${shotIndex} · ${result}`;
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

    if (loading || !recording) {
        return <div className="loading">{t('replay.loading')}</div>;
    }

    const handleDelete = async () => {
        if (!window.confirm(t('replay.deleteConfirm'))) {
            return;
        }

        try {
            const response = await fetch(`/api/recordings/${gameId}`, {
                method: 'DELETE'
            });

            if (response.ok || response.status === 204) {
                alert(t('replay.deleted'));
                if (onBack) {
                    onBack();
                }
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
        <div className="replay-player">
            {/* 頁首 */}
            <div className="player-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← {t('common.back')}
                    </button>
                )}
                <h1>{t('replay.playerTitle')}</h1>
                <span className="game-id">{gameId}</span>
                <button className="delete-button" onClick={handleDelete}>
                    {t('replay.delete')}
                </button>
            </div>

            <div className="player-content">
                <div className="video-section">
                    {videoError ? (
                        <div className="video-unavailable">
                            <strong>影片檔無法播放</strong>
                            <span>後端找不到或無法讀取對應影片檔，請確認 video.mp4 在 recordings 資料夾中。</span>
                        </div>
                    ) : (
                        <video
                            className="video-player"
                            controls
                            src={`/api/recordings/${gameId}/video`}
                            onError={() => setVideoError(true)}
                        >
                            {t('replay.videoUnsupported')}
                        </video>
                    )}

                    {/* 事件時間軸 */}
                    <div className="event-timeline">
                        <h3>{t('replay.eventTimeline')}</h3>
                        <div className="timeline-events">
                            {events.map((event) => (
                                <div key={event.id} className="timeline-event">
                                    <span className="event-type">{formatEventLabel(event)}</span>
                                    <span className="event-time">
                                        {formatDuration(getEventOffset(event))}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* 資訊面板 */}
                <div className="info-panel">
                    <div className="info-section">
                        <h3>{t('replay.gameInfo')}</h3>
                        <div className="info-item">
                            <span className="info-label">{t('replay.type')}:</span>
                            <span className="info-value">
                                {recording.game_type === 'nine_ball' ? t('replay.nineBallBattle') : t('replay.practiceMode')}
                            </span>
                        </div>
                        <div className="info-item">
                            <span className="info-label">{t('replay.date')}:</span>
                            <span className="info-value">{formatDate(recording)}</span>
                        </div>
                        <div className="info-item">
                            <span className="info-label">{t('replay.duration')}:</span>
                            <span className="info-value">{formatDuration(recording.duration_seconds)}</span>
                        </div>
                    </div>

                    {recording.game_type === 'nine_ball' && (
                        <div className="info-section">
                            <h3>{t('replay.battleInfo')}</h3>
                            <div className="player-info">
                                <div className="player-row">
                                    <span className="player-name">{recording.player1_name}</span>
                                    <span className="player-score">{recording.player1_score}</span>
                                </div>
                                <div className="vs-divider">VS</div>
                                <div className="player-row">
                                    <span className="player-name">{recording.player2_name}</span>
                                    <span className="player-score">{recording.player2_score}</span>
                                </div>
                            </div>
                            {recording.winner && (
                                <div className="winner-info">
                                    {t('replay.winner')}: {recording.winner}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ReplayPlayer;
