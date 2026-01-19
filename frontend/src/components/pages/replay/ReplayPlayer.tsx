/**
 * 回放播放器
 * 
 * 播放錄影影片（H.264 格式）
 * 顯示遊戲資訊和事件時間軸
 */

import React, { useState, useEffect } from 'react';
import './ReplayPlayer.css';

interface Event {
    id: number;
    timestamp: number;
    event_type: string;
    data: any;
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
}

interface ReplayPlayerProps {
    gameId: string;
    onBack?: () => void;
}

const ReplayPlayer: React.FC<ReplayPlayerProps> = ({ gameId, onBack }) => {
    const [recording, setRecording] = useState<Recording | null>(null);
    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
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

    if (loading || !recording) {
        return <div className="loading">載入中...</div>;
    }

    return (
        <div className="replay-player">
            {/* 頁首 */}
            <div className="player-header">
                {onBack && (
                    <button className="back-button" onClick={onBack}>
                        ← 返回
                    </button>
                )}
                <h1>回放播放器</h1>
                <span className="game-id">{gameId}</span>
            </div>

            <div className="player-content">
                {/* 影片播放區 */}
                <div className="video-section">
                    <video
                        className="video-player"
                        controls
                        src={`/replay/burnin/${gameId}.mp4`}
                    >
                        您的瀏覽器不支援影片播放
                    </video>

                    {/* 事件時間軸 */}
                    <div className="event-timeline">
                        <h3>事件時間軸</h3>
                        <div className="timeline-events">
                            {events.map((event) => (
                                <div key={event.id} className="timeline-event">
                                    <span className="event-type">{event.event_type}</span>
                                    <span className="event-time">
                                        {formatDuration(event.timestamp - new Date(recording.start_time).getTime() / 1000)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* 資訊面板 */}
                <div className="info-panel">
                    <div className="info-section">
                        <h3>遊戲資訊</h3>
                        <div className="info-item">
                            <span className="info-label">類型:</span>
                            <span className="info-value">
                                {recording.game_type === 'nine_ball' ? '9球對戰' : '練習模式'}
                            </span>
                        </div>
                        <div className="info-item">
                            <span className="info-label">日期:</span>
                            <span className="info-value">{formatDate(recording.start_time)}</span>
                        </div>
                        <div className="info-item">
                            <span className="info-label">時長:</span>
                            <span className="info-value">{formatDuration(recording.duration_seconds)}</span>
                        </div>
                    </div>

                    {recording.game_type === 'nine_ball' && (
                        <div className="info-section">
                            <h3>對戰資訊</h3>
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
                                    勝者: {recording.winner}
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
