/**
 * CameraParamsPage Component - 相機參數設定頁面
 * 提供完整的相機參數控制介面
 */

import React, { useState, useEffect, useMemo } from 'react';
import './CameraParamsPage.css';

interface CameraParams {
    exposure: number;
    iso: number;
    brightness: number;
    contrast: number;
    saturation: number;
    sharpness: number;
    auto_wb: boolean;
    wb_temp: number;
    denoise_enabled: boolean;
    denoise_strength: number;
    denoise_method: string;
    brightness_adjust: number;
    contrast_adjust: number;
}

interface FormatInfo {
    format: string;
    description: string;
    is_compressed: boolean;
    warning: string | null;
    recommendation: string;
}

interface CameraParamsPageProps {
    onBack?: () => void;
}

export const CameraParamsPage: React.FC<CameraParamsPageProps> = ({ onBack }) => {
    const [params, setParams] = useState<CameraParams | null>(null);
    const [formatInfo, setFormatInfo] = useState<FormatInfo | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [message, setMessage] = useState('');

    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';
    const streamRef = React.useRef<HTMLImageElement>(null);

    useEffect(() => {
        // 並行請求,加快載入速度
        Promise.all([fetchParams(), fetchFormatInfo()]);

        // Cleanup: 元件卸載時處理
        return () => {
            // 使用更溫和的方式清理,避免影響其他頁面的串流
            if (streamRef.current) {
                streamRef.current.onerror = null;
                streamRef.current.onload = null;
            }
        };
    }, []);

    const fetchParams = async () => {
        try {
            const response = await fetch(`${backendUrl}/api/camera/params`);
            if (response.ok) {
                const data = await response.json();
                setParams(data);
            } else {
                // 如果API失敗,設置預設值避免一直載入
                console.error('Failed to fetch params');
                setParams({
                    exposure: -5,
                    iso: 0,
                    brightness: 128,
                    contrast: 128,
                    saturation: 128,
                    sharpness: 128,
                    auto_wb: true,
                    wb_temp: 4500,
                    denoise_enabled: false,
                    denoise_strength: 50,
                    denoise_method: 'bilateral',
                    brightness_adjust: 0,
                    contrast_adjust: 0
                });
            }
        } catch (error) {
            console.error('Error fetching camera params:', error);
            // 設置預設值
            setParams({
                exposure: -5,
                iso: 0,
                brightness: 128,
                contrast: 128,
                saturation: 128,
                sharpness: 128,
                auto_wb: true,
                wb_temp: 4500,
                denoise_enabled: false,
                denoise_strength: 50,
                denoise_method: 'bilateral',
                brightness_adjust: 0,
                contrast_adjust: 0
            });
        }
    };

    const fetchFormatInfo = async () => {
        try {
            const response = await fetch(`${backendUrl}/api/camera/format`);
            if (response.ok) {
                const data = await response.json();
                setFormatInfo(data);
            }
        } catch (error) {
            console.error('Error fetching format info:', error);
        }
    };

    // 防抖處理 - 避免滑桿卡頓
    const debounceTimerRef = React.useRef<NodeJS.Timeout | null>(null);

    const updateParam = async (key: string, value: any, immediate = false) => {
        // 立即更新本地狀態,避免卡頓
        setParams(prev => prev ? { ...prev, [key]: value } : null);

        // 清除之前的計時器
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // 如果是立即更新(checkbox等),直接發送請求
        if (immediate) {
            await sendUpdateRequest(key, value);
            return;
        }

        // 否則使用防抖,200ms後才發送請求
        debounceTimerRef.current = setTimeout(async () => {
            await sendUpdateRequest(key, value);
        }, 200);
    };

    const sendUpdateRequest = async (key: string, value: any) => {
        setIsLoading(true);
        try {
            const response = await fetch(`${backendUrl}/api/camera/params`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [key]: value })
            });

            if (response.ok) {
                const result = await response.json();

                if (result.warnings && result.warnings.length > 0) {
                    setMessage(`⚠ ${result.warnings.join(', ')}`);
                } else {
                    setMessage('✓ 參數已更新');
                }
                setTimeout(() => setMessage(''), 2000);
            }
        } catch (error) {
            setMessage('✗ 更新失敗');
            setTimeout(() => setMessage(''), 2000);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAutoAdjust = async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`${backendUrl}/api/camera/auto-adjust`, {
                method: 'POST'
            });

            if (response.ok) {
                const data = await response.json();

                // 使用後端回傳的實際參數更新UI
                if (data.adjusted_params) {
                    const newParams = params ? {
                        ...params,
                        ...data.adjusted_params
                    } : data.adjusted_params;

                    setParams(newParams);
                }

                setMessage('✓ 自動調整已啟用');
                setTimeout(() => setMessage(''), 2000);
            }
        } catch (error) {
            setMessage('✗ 自動調整失敗');
            setTimeout(() => setMessage(''), 2000);
        } finally {
            setIsLoading(false);
        }
    };

    // 使用 useMemo 確保 params 更新時重新計算 displayParams
    const displayParams = useMemo(() => {
        return params || {
            exposure: -5,
            iso: 0,
            brightness: 128,
            contrast: 128,
            saturation: 128,
            sharpness: 128,
            auto_wb: true,
            wb_temp: 4500,
            denoise_enabled: false,
            denoise_strength: 50,
            denoise_method: 'bilateral',
            brightness_adjust: 0,
            contrast_adjust: 0
        };
    }, [params]);

    return (
        <div className="camera-params-page">
            {/* 頁面標題 */}
            <div className="page-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {onBack && (
                        <button
                            onClick={onBack}
                            className="btn btn-secondary"
                            style={{ padding: '8px 16px' }}
                        >
                            ← 返回
                        </button>
                    )}
                    <h2>相機參數設定</h2>
                </div>
                <p className="page-subtitle">調整相機參數以優化影像品質</p>
            </div>

            {/* 訊息顯示 */}
            {message && (
                <div className={`message ${message.startsWith('✓') ? 'success' : message.startsWith('⚠') ? 'warning' : 'error'}`}>
                    {message}
                </div>
            )}

            <div className="params-container" key={`params-${displayParams.exposure}-${displayParams.brightness}`}>
                {/* 左側: 即時影像預覽 */}
                <div className="preview-section">
                    <h3>相機即時預覽</h3>
                    <div className="preview-container">
                        <img
                            ref={streamRef}
                            src={`${backendUrl}/burnin/camera1.mjpg?quality=med`}
                            alt="相機即時畫面"
                            className="camera-stream"
                        />
                    </div>
                    <p className="hint">即時顯示相機畫面,參數調整會立即反映在影像上</p>
                </div>

                {/* 右側: 參數控制 */}
                <div className="camera-params-settings">
                    {/* 格式資訊警告 */}
                    {formatInfo?.is_compressed && (
                        <div className="format-warning">
                            <span className="warning-icon">⚠</span>
                            <div className="warning-content">
                                <div className="warning-text">{formatInfo.warning}</div>
                                <div className="recommendation-text">{formatInfo.recommendation}</div>
                                <div className="format-detail">
                                    當前格式: {formatInfo.format} ({formatInfo.description})
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 軟體降噪 */}
                    <div className="param-section">
                        <h4>軟體降噪</h4>
                        <div className="param-row">
                            <label className="param-label">
                                <input
                                    type="checkbox"
                                    checked={displayParams.denoise_enabled}
                                    onChange={(e) => updateParam('denoise_enabled', e.target.checked, true)}
                                    disabled={isLoading}
                                />
                                啟用降噪
                            </label>
                        </div>

                        {displayParams.denoise_enabled && (
                            <>
                                <div className="param-row">
                                    <label className="param-label">降噪強度: {displayParams.denoise_strength}</label>
                                    <input
                                        type="range"
                                        min="0"
                                        max="100"
                                        value={displayParams.denoise_strength}
                                        onChange={(e) => updateParam('denoise_strength', parseInt(e.target.value))}
                                        disabled={isLoading}
                                        className="param-slider"
                                    />
                                </div>

                                <div className="param-row">
                                    <label className="param-label">降噪演算法</label>
                                    <select
                                        value={displayParams.denoise_method}
                                        onChange={(e) => updateParam('denoise_method', e.target.value, true)}
                                        disabled={isLoading}
                                        className="param-select"
                                    >
                                        <option value="median">中值濾波 (推薦)</option>
                                        <option value="bilateral">雙邊濾波 (預設)</option>
                                        <option value="gaussian">高斯模糊 (最快)</option>
                                        <option value="morphology">形態學降噪 (極快)</option>
                                        <option value="fastNlMeansGray">快速非局部平均-灰階</option>
                                        <option value="fastNlMeans">快速非局部平均-彩色 (慢)</option>
                                    </select>
                                </div>
                            </>
                        )}
                    </div>

                    {/* 曝光設定 */}
                    <div className="param-section">
                        <h4>曝光設定</h4>
                        <div className="param-row">
                            <label className="param-label">曝光時間: {displayParams.exposure}</label>
                            <input
                                type="range"
                                min="-20"
                                max="1"
                                step="0.1"
                                value={displayParams.exposure}
                                onChange={(e) => updateParam('exposure', parseFloat(e.target.value))}
                                disabled={isLoading}
                                className="param-slider"
                            />
                        </div>

                        <div className="param-row">
                            <label className="param-label">
                                ISO 感光度: {displayParams.iso === 0 ? '自動' : displayParams.iso}
                            </label>
                            <input
                                type="range"
                                min="0"
                                max="3200"
                                step="100"
                                value={displayParams.iso}
                                onChange={(e) => updateParam('iso', parseInt(e.target.value))}
                                disabled={isLoading}
                                className="param-slider"
                            />
                        </div>
                    </div>

                    {/* 影像調整 */}
                    <div className="param-section">
                        <h4>影像調整</h4>
                        <div className="param-row">
                            <label className="param-label">亮度: {displayParams.brightness}</label>
                            <input
                                type="range"
                                min="0"
                                max="255"
                                value={displayParams.brightness}
                                onChange={(e) => updateParam('brightness', parseInt(e.target.value))}
                                disabled={isLoading}
                                className="param-slider"
                            />
                        </div>

                        <div className="param-row">
                            <label className="param-label">對比度: {displayParams.contrast}</label>
                            <input
                                type="range"
                                min="0"
                                max="255"
                                value={displayParams.contrast}
                                onChange={(e) => updateParam('contrast', parseInt(e.target.value))}
                                disabled={isLoading}
                                className="param-slider"
                            />
                        </div>

                        <div className="param-row">
                            <label className="param-label">飽和度: {displayParams.saturation}</label>
                            <input
                                type="range"
                                min="0"
                                max="255"
                                value={displayParams.saturation}
                                onChange={(e) => updateParam('saturation', parseInt(e.target.value))}
                                disabled={isLoading}
                                className="param-slider"
                            />
                        </div>
                    </div>

                    {/* 白平衡 */}
                    <div className="param-section">
                        <h4>白平衡</h4>
                        <div className="param-row">
                            <label className="param-label">
                                <input
                                    type="checkbox"
                                    checked={displayParams.auto_wb}
                                    onChange={(e) => updateParam('auto_wb', e.target.checked, true)}
                                    disabled={isLoading}
                                />
                                自動白平衡
                            </label>
                        </div>

                        {!displayParams.auto_wb && (
                            <div className="param-row">
                                <label className="param-label">色溫: {displayParams.wb_temp}K</label>
                                <input
                                    type="range"
                                    min="2800"
                                    max="6500"
                                    step="100"
                                    value={displayParams.wb_temp}
                                    onChange={(e) => updateParam('wb_temp', parseInt(e.target.value))}
                                    disabled={isLoading}
                                    className="param-slider"
                                />
                            </div>
                        )}
                    </div>

                    {/* 自動調整 */}
                    <div className="param-section">
                        <button
                            className="btn btn-primary auto-adjust-btn"
                            onClick={handleAutoAdjust}
                            disabled={isLoading}
                        >
                            自動調整所有參數
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
