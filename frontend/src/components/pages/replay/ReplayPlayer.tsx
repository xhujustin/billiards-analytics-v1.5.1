/**
 * 回放播放器
 *
 * 播放錄影影片並顯示事件時間軸。
 */

import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './ReplayPlayer.css';

interface Event {
    id: number;
    timestamp: number;
    offset_seconds?: number | null;
    event_type: string;
    data: {
        shot_index?: number;
        potted_balls?: unknown[];
        pocket_result?: string;
        cue_ball_potted?: boolean;
        is_foul?: boolean;
    } | null;
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
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const [recording, setRecording] = useState<Recording | null>(null);
    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);
    const [videoError, setVideoError] = useState(false);
    const [currentVideoTime, setCurrentVideoTime] = useState(0);

    useEffect(() => {
        setLoading(true);
        setVideoError(false);
        setCurrentVideoTime(0);
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

        const startTimestamp = new Date(recording?.start_time || '').getTime() / 1000;
        const offset = event.timestamp - startTimestamp;
        return Number.isFinite(offset) ? offset : 0;
    };

    const clampPlaybackTime = (seconds: number): number => {
        const duration = videoRef.current?.duration || recording?.duration_seconds || 0;
        const maxTime = Number.isFinite(duration) && duration > 0 ? duration : Number.MAX_SAFE_INTEGER;
        return Math.min(Math.max(seconds, 0), maxTime);
    };

    const handleSeekToEvent = (event: Event) => {
        const video = videoRef.current;
        if (!video) {
            return;
        }

        const targetTime = clampPlaybackTime(getEventOffset(event));
        video.currentTime = targetTime;
        setCurrentVideoTime(targetTime);
        video.focus();
    };

    const isCurrentEvent = (event: Event): boolean => {
        return Math.abs(currentVideoTime - clampPlaybackTime(getEventOffset(event))) < 1;
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
                ? '母球落袋'
                : pottedBalls.length > 0 || event.data?.pocket_result === 'made'
                    ? '進球'
                    : '未進';

        return `擊球${shotIndex} - ${result}`;
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

    if (loading || !recording) {
        return <div className="loading">{t('replay.loading')}</div>;
    }

    return (
        <div className="replay-player">
            <div className="player-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        {t('common.back')}
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
                            <strong>影片無法播放</strong>
                            <span>請確認此回放已有可播放的 video.mp4，且 recordings 資料路徑正確。</span>
                        </div>
                    ) : (
                        <video
                            ref={videoRef}
                            className="video-player"
                            controls
                            src={`/api/recordings/${gameId}/video`}
                            onError={() => setVideoError(true)}
                            onTimeUpdate={(event) => setCurrentVideoTime(event.currentTarget.currentTime)}
                        >
                            {t('replay.videoUnsupported')}
                        </video>
                    )}

                    <div className="event-timeline">
                        <h3>{t('replay.eventTimeline')}</h3>
                        <div className="timeline-events">
                            {events.map((event) => {
                                const eventOffset = clampPlaybackTime(getEventOffset(event));
                                return (
                                    <button
                                        key={event.id}
                                        type="button"
                                        className={`timeline-event${isCurrentEvent(event) ? ' timeline-event-active' : ''}`}
                                        onClick={() => handleSeekToEvent(event)}
                                        title={`跳轉到 ${formatDuration(eventOffset)}`}
                                    >
                                        <span className="event-type">{formatEventLabel(event)}</span>
                                        <span className="event-time">
                                            {formatDuration(eventOffset)}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>

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
