/**
 * AutoCalibrationPage Component - 投影機自動校正頁面
 * 兩頁式流程: 1. 定位 ArUco 標記  2. 檢測與確認
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './AutoCalibrationPage.css';

type CornerPosition = 'top-left' | 'top-right' | 'bottom-right' | 'bottom-left';

interface Point {
    x: number;
    y: number;
}

interface DetectionResult {
    detected: boolean;
    corners?: number[][];
    marker_ids?: number[];
    message: string;
}

interface AutoCalibrationPageProps {
    onBack?: () => void;
    burninUrl?: string;
}

export const AutoCalibrationPage: React.FC<AutoCalibrationPageProps> = ({ onBack, burninUrl }) => {
    const { t } = useTranslation();
    const [currentPage, setCurrentPage] = useState<1 | 2>(1);
    const [selectedCorner, setSelectedCorner] = useState<CornerPosition>('top-left');
    const [offsets, setOffsets] = useState({
        'top-left': { x: -300, y: -300 },
        'top-right': { x: 300, y: -300 },
        'bottom-right': { x: 300, y: 300 },
        'bottom-left': { x: -300, y: 300 }
    });
    const [detectionResult, setDetectionResult] = useState<DetectionResult | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [message, setMessage] = useState('');


    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

    const cornerLabels: Record<CornerPosition, string> = {
        'top-left': t('settings.projectorCalibration.topLeft'),
        'top-right': t('settings.projectorCalibration.topRight'),
        'bottom-left': t('settings.projectorCalibration.bottomLeft'),
        'bottom-right': t('settings.projectorCalibration.bottomRight'),
    };

    // 鍵盤控制
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (currentPage !== 1) return;

            const step = 20;
            const newOffsets = { ...offsets };

            switch (e.key) {
                case 'ArrowUp':
                    newOffsets[selectedCorner].y -= step;
                    break;
                case 'ArrowDown':
                    newOffsets[selectedCorner].y += step;
                    break;
                case 'ArrowLeft':
                    newOffsets[selectedCorner].x -= step;
                    break;
                case 'ArrowRight':
                    newOffsets[selectedCorner].x += step;
                    break;
                default:
                    return;
            }

            e.preventDefault();
            setOffsets(newOffsets);
            updateProjectorPosition(selectedCorner, newOffsets[selectedCorner]);
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [currentPage, selectedCorner, offsets]);

    // 啟動校正
    useEffect(() => {
        startCalibration();
        return () => {
            // 清理: 切換回待機模式
            fetch(`${backendUrl}/api/projector/mode`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'idle' })
            });
        };
    }, []);

    const startCalibration = async () => {
        try {
            const response = await fetch(`${backendUrl}/api/calibration/start`, {
                method: 'POST'
            });
            if (response.ok) {
                setMessage(t('settings.projectorCalibration.started'));
            }
        } catch (error) {
            console.error('Failed to start calibration:', error);
            setMessage(t('settings.projectorCalibration.startFailed'));
        }
    };

    const moveCorner = async (direction: 'up' | 'down' | 'left' | 'right') => {
        const step = 20;
        const newOffsets = { ...offsets };

        switch (direction) {
            case 'up': newOffsets[selectedCorner].y -= step; break;
            case 'down': newOffsets[selectedCorner].y += step; break;
            case 'left': newOffsets[selectedCorner].x -= step; break;
            case 'right': newOffsets[selectedCorner].x += step; break;
        }

        setOffsets(newOffsets);
        await updateProjectorPosition(selectedCorner, newOffsets[selectedCorner]);
    };

    const updateProjectorPosition = async (corner: CornerPosition, offset: Point) => {
        try {
            await fetch(`${backendUrl}/api/calibration/move-corner`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ corner, offset })
            });
        } catch (error) {
            console.error('Failed to update position:', error);
        }
    };

    const confirmAndContinue = async () => {
        setIsLoading(true);
        setMessage(t('settings.projectorCalibration.detecting'));

        try {
            const response = await fetch(`${backendUrl}/api/calibration/detect`);
            const result: DetectionResult = await response.json();

            setDetectionResult(result);

            if (result.detected) {
                setCurrentPage(2);
                setMessage(t('settings.projectorCalibration.detectSuccess'));
            } else {
                setMessage(result.message || t('settings.projectorCalibration.markerNotDetectedAdjust'));
            }
        } catch (error) {
            console.error('Detection failed:', error);
            setMessage(t('settings.projectorCalibration.detectFailedRetry'));
        } finally {
            setIsLoading(false);
        }
    };

    const confirmCalibration = async () => {
        setIsLoading(true);
        setMessage(t('settings.projectorCalibration.computingMatrix'));

        try {
            const response = await fetch(`${backendUrl}/api/calibration/confirm`, {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                setMessage(t('settings.projectorCalibration.completedWithBounds', { width: result.bounds.width, height: result.bounds.height }));

                // 200MS返回設定頁面
                setTimeout(() => {
                    if (onBack) {
                        onBack();
                    }
                }, 200);
            } else {
                setMessage(t('settings.projectorCalibration.calibrationFailedRetry'));
            }
        } catch (error) {
            console.error('Calibration failed:', error);
            setMessage(t('settings.projectorCalibration.calibrationFailed'));
        } finally {
            setIsLoading(false);
        }
    };

    const saveAndExit = async () => {
        setIsLoading(true);
        setMessage(t('settings.projectorCalibration.detectingAndSaving'));

        try {
            const detectResponse = await fetch(`${backendUrl}/api/calibration/detect`);
            const detectResult: DetectionResult = await detectResponse.json();
            setDetectionResult(detectResult);

            if (!detectResult.detected) {
                setMessage(detectResult.message || t('settings.projectorCalibration.markerNotDetectedAdjust'));
                return;
            }

            const confirmResponse = await fetch(`${backendUrl}/api/calibration/confirm`, {
                method: 'POST'
            });

            if (!confirmResponse.ok) {
                setMessage(t('settings.projectorCalibration.calibrationFailedRetry'));
                return;
            }

            const result = await confirmResponse.json();
            setMessage(t('settings.projectorCalibration.completedWithBounds', { width: result.bounds.width, height: result.bounds.height }));
            window.setTimeout(() => {
                onBack?.();
            }, 200);
        } catch (error) {
            console.error('Calibration save failed:', error);
            setMessage(t('settings.projectorCalibration.saveFailedRetry'));
        } finally {
            setIsLoading(false);
        }
    };

    const resetPositions = () => {
        const defaultOffsets = {
            'top-left': { x: -300, y: -300 },
            'top-right': { x: 300, y: -300 },
            'bottom-right': { x: 300, y: 300 },
            'bottom-left': { x: -300, y: 300 }
        };
        setOffsets(defaultOffsets);

        // 更新所有標記位置
        Object.entries(defaultOffsets).forEach(([corner, offset]) => {
            updateProjectorPosition(corner as CornerPosition, offset);
        });
    };

    return (
        <div className="auto-calibration-page">
            <div className="calibration-header">
                <div className="progress-indicator">
                    {t('settings.projectorCalibration.stepLabel', {
                        current: currentPage,
                        total: 2,
                        label: currentPage === 1
                            ? t('settings.projectorCalibration.positionMarkers')
                            : t('settings.projectorCalibration.detectAndConfirm'),
                    })}
                </div>
            </div>

            {message && (
                <div className={`message ${detectionResult?.detected ? 'success' : 'info'}`}>
                    {message}
                </div>
            )}

            {currentPage === 1 && (
                <div className="page-1">
                    <div className="projector-preview-section">
                        <h2>{t('settings.projectorCalibration.livePreview')}</h2>
                        <div className="preview-container">
                            <img
                                src={burninUrl ? `${burninUrl}&client_id=auto-calibration-monitor` : `${backendUrl}/burnin/camera1.mjpg?quality=med&client_id=auto-calibration-monitor`}
                                alt={t('settings.projectorCalibration.liveImageAlt')}
                                className="projector-stream"
                            />
                        </div>
                        <p className="hint">{t('settings.projectorCalibration.markerAlignHint')}</p>
                    </div>

                    <div className="control-section">
                        <div className="corner-selector projector-control-card">
                            <div className="current-control">
                                <strong>{t('settings.projectorCalibration.currentControl')}</strong> {t('settings.projectorCalibration.markerLabel', { corner: cornerLabels[selectedCorner] })}
                                <span className="coordinates">
                                    ({offsets[selectedCorner].x}, {offsets[selectedCorner].y})
                                </span>
                            </div>
                            <div className="corner-buttons">
                                {(Object.keys(cornerLabels) as CornerPosition[]).map(corner => (
                                    <button
                                        key={corner}
                                        className={selectedCorner === corner ? 'active' : ''}
                                        onClick={() => setSelectedCorner(corner)}
                                    >
                                        {cornerLabels[corner]}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="direction-controls">
                            <label>{t('settings.projectorCalibration.moveControls')}</label>
                            <div className="d-pad">
                                <button onClick={() => moveCorner('up')} className="up">↑</button>
                                <button onClick={() => moveCorner('left')} className="left">←</button>
                                <button onClick={() => moveCorner('down')} className="down">↓</button>
                                <button onClick={() => moveCorner('right')} className="right">→</button>
                            </div>
                            <p className="hint">{t('settings.projectorCalibration.keyboardHint')}</p>
                        </div>
                    </div>

                    <div className="actions">
                        <button onClick={resetPositions} className="secondary">
                            {t('settings.projectorCalibration.resetPosition')}
                        </button>
                        <button onClick={onBack} className="secondary">
                            {t('settings.projectorCalibration.close')}
                        </button>
                        <button
                            onClick={saveAndExit}
                            className="primary"
                            disabled={isLoading}
                        >
                            {isLoading ? t('settings.projectorCalibration.saving') : t('settings.projectorCalibration.saveAndExit')}
                        </button>
                    </div>
                </div>
            )}

            {currentPage === 2 && (
                <div className="page-2">
                    <div className="camera-preview-section">
                        <h3>{t('settings.projectorCalibration.cameraDetectionView')}</h3>
                        <div className="preview-container">
                            <img
                                src={`${backendUrl}/api/calibration/preview`}
                                alt={t('settings.projectorCalibration.cameraDetectionAlt')}
                                className="camera-stream"
                                key={Date.now()} // 強制重新載入
                            />
                        </div>
                        <p className="hint">{t('settings.projectorCalibration.previewHint')}</p>
                    </div>

                    <div className="detection-status">
                        {detectionResult?.detected ? (
                            <>
                                <div className="status-ok">{t('settings.projectorCalibration.markersDetected')}</div>
                                <div className="coordinates-list">
                                    <h4>{t('settings.projectorCalibration.detectedCoordinates')}</h4>
                                    {detectionResult.corners?.map((corner, i) => (
                                        <div key={i} className="coordinate-item">
                                            {[t('settings.projectorCalibration.topLeft'), t('settings.projectorCalibration.topRight'), t('settings.projectorCalibration.bottomRight'), t('settings.projectorCalibration.bottomLeft')][i]}: ({Math.round(corner[0])}, {Math.round(corner[1])})
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="status-error">{t('settings.projectorCalibration.markerNotDetectedBack')}</div>
                        )}
                    </div>

                    <div className="actions">
                        <button onClick={() => setCurrentPage(1)} className="secondary">
                            {t('settings.projectorCalibration.backToAdjust')}
                        </button>
                        <button onClick={confirmAndContinue} className="secondary">
                            {t('settings.projectorCalibration.redetect')}
                        </button>
                        <button
                            onClick={confirmCalibration}
                            className="primary"
                            disabled={!detectionResult?.detected || isLoading}
                        >
                            {isLoading ? t('settings.projectorCalibration.calibrating') : t('settings.projectorCalibration.confirmCalibration')}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};
