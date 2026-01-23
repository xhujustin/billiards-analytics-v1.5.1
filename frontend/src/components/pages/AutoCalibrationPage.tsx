/**
 * AutoCalibrationPage Component - 投影機自動校正頁面
 * 兩頁式流程: 1. 定位 ArUco 標記  2. 檢測與確認
 */

import React, { useState, useEffect, useRef } from 'react';
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

export const AutoCalibrationPage: React.FC = () => {
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
    const previewIntervalRef = useRef<number | null>(null);

    const cornerLabels: Record<CornerPosition, string> = {
        'top-left': '左上',
        'top-right': '右上',
        'bottom-right': '右下',
        'bottom-left': '左下'
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
                setMessage('校正已啟動,請調整標記位置');
            }
        } catch (error) {
            console.error('Failed to start calibration:', error);
            setMessage('啟動校正失敗');
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
        setMessage('檢測中...');

        try {
            const response = await fetch(`${backendUrl}/api/calibration/detect`);
            const result: DetectionResult = await response.json();

            setDetectionResult(result);

            if (result.detected) {
                setCurrentPage(2);
                setMessage('檢測成功!請確認投影範圍');
            } else {
                setMessage(result.message || '未檢測到標記,請調整位置');
            }
        } catch (error) {
            console.error('Detection failed:', error);
            setMessage('檢測失敗,請重試');
        } finally {
            setIsLoading(false);
        }
    };

    const confirmCalibration = async () => {
        setIsLoading(true);
        setMessage('計算校準矩陣中...');

        try {
            const response = await fetch(`${backendUrl}/api/calibration/confirm`, {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                setMessage(`校正完成! 投影範圍: ${result.bounds.width}×${result.bounds.height}`);

                // 3秒後返回設定頁面
                setTimeout(() => {
                    window.history.back();
                }, 3000);
            } else {
                setMessage('校正失敗,請重試');
            }
        } catch (error) {
            console.error('Calibration failed:', error);
            setMessage('校正失敗');
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
                <h2>投影機自動校正</h2>
                <div className="progress-indicator">
                    步驟 {currentPage}/2: {currentPage === 1 ? '定位 ArUco 標記' : '檢測與確認'}
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
                        <h3>投影機畫面預覽</h3>
                        <div className="preview-container">
                            <img
                                src={`${backendUrl}/burnin/projector.mjpg`}
                                alt="投影機畫面"
                                className="projector-stream"
                            />
                        </div>
                        <p className="hint">投影機會顯示 4 個 ArUco 標記,請調整位置對齊球桌</p>
                    </div>

                    <div className="control-section">
                        <div className="current-control">
                            <strong>目前控制:</strong> {cornerLabels[selectedCorner]}標記
                            <span className="coordinates">
                                ({offsets[selectedCorner].x}, {offsets[selectedCorner].y})
                            </span>
                        </div>

                        <div className="corner-selector">
                            <label>選擇標記:</label>
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
                            <label>移動控制:</label>
                            <div className="d-pad">
                                <button onClick={() => moveCorner('up')} className="up">↑</button>
                                <div className="middle-row">
                                    <button onClick={() => moveCorner('left')} className="left">←</button>
                                    <div className="center">●</div>
                                    <button onClick={() => moveCorner('right')} className="right">→</button>
                                </div>
                                <button onClick={() => moveCorner('down')} className="down">↓</button>
                            </div>
                            <p className="hint">提示: 可使用鍵盤方向鍵操作 (步長: 20px)</p>
                        </div>
                    </div>

                    <div className="actions">
                        <button onClick={resetPositions} className="secondary">
                            重置位置
                        </button>
                        <button
                            onClick={confirmAndContinue}
                            className="primary"
                            disabled={isLoading}
                        >
                            {isLoading ? '檢測中...' : '確認並繼續 →'}
                        </button>
                    </div>
                </div>
            )}

            {currentPage === 2 && (
                <div className="page-2">
                    <div className="camera-preview-section">
                        <h3>相機檢測畫面</h3>
                        <div className="preview-container">
                            <img
                                src={`${backendUrl}/api/calibration/preview`}
                                alt="相機檢測畫面"
                                className="camera-stream"
                                key={Date.now()} // 強制重新載入
                            />
                        </div>
                        <p className="hint">綠色框線顯示投影範圍,白色填充為預覽效果</p>
                    </div>

                    <div className="detection-status">
                        {detectionResult?.detected ? (
                            <>
                                <div className="status-ok">✓ 已檢測到 4 個 ArUco 標記</div>
                                <div className="coordinates-list">
                                    <h4>檢測座標:</h4>
                                    {detectionResult.corners?.map((corner, i) => (
                                        <div key={i} className="coordinate-item">
                                            {['左上', '右上', '右下', '左下'][i]}: ({Math.round(corner[0])}, {Math.round(corner[1])})
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="status-error">✗ 未檢測到標記,請返回調整</div>
                        )}
                    </div>

                    <div className="actions">
                        <button onClick={() => setCurrentPage(1)} className="secondary">
                            ← 返回調整
                        </button>
                        <button onClick={confirmAndContinue} className="secondary">
                            重新檢測
                        </button>
                        <button
                            onClick={confirmCalibration}
                            className="primary"
                            disabled={!detectionResult?.detected || isLoading}
                        >
                            {isLoading ? '校正中...' : '確認校正 ✓'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};
