/**
 * MetadataPage Component - Metadata 數據頁面
 */

import React from 'react';
import type { MetadataUpdate } from '../../sdk/types';
import './MetadataPage.css';

interface MetadataPageProps {
  metadata: MetadataUpdate | null;
}

export const MetadataPage: React.FC<MetadataPageProps> = ({ metadata }) => {
  if (!metadata) {
    return (
      <div className="metadata-page">
        <h2 className="page-title">📈 即時數據監控 (Metadata)</h2>
        <div className="card">
          <p className="no-data">等待數據...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="metadata-page">
      <h2 className="page-title">📈 即時數據監控 (Metadata)</h2>

      {/* 基本指標 */}
      <div className="card">
        <h3 className="card-title">基本指標</h3>
        <div className="metrics">
          <div className="metric-row">
            <span className="metric-label">Frame ID:</span>
            <span className="metric-value">{metadata.frame_id}</span>
          </div>
          <div className="metric-row">
            <span className="metric-label">檢測數量:</span>
            <span className="metric-value">{metadata.detected_count} 個物件</span>
          </div>
          <div className="metric-row">
            <span className="metric-label">追蹤狀態:</span>
            <span className={`metric-value ${metadata.tracking_state === 'active' ? 'active' : ''}`}>
              {metadata.tracking_state === 'active' ? '● ' : '○ '}
              {metadata.tracking_state}
            </span>
          </div>
          <div className="metric-row">
            <span className="metric-label">更新頻率:</span>
            <span className="metric-value">{metadata.rate_hz} Hz</span>
          </div>
          {metadata.ar_paths && metadata.ar_paths.length > 0 && (
            <div className="metric-row">
              <span className="metric-label">AR 路徑數:</span>
              <span className="metric-value">{metadata.ar_paths.length} 條</span>
            </div>
          )}
        </div>
      </div>

      {/* 檢測物件列表 */}
      {metadata.detections && metadata.detections.length > 0 && (
        <div className="card">
          <h3 className="card-title">檢測物件列表</h3>
          <div className="detections">
            {metadata.detections.map((detection, index) => (
              <div key={index} className="detection-item">
                <span className="detection-index">#{index + 1}</span>
                <span className="detection-label">{detection.label || '未知'}</span>
                <span className="detection-confidence">
                  信心度: {((detection.score || 0) * 100).toFixed(0)}%
                </span>
                {detection.bbox && (
                  <span className="detection-bbox">
                    [x:{detection.bbox[0]}, y:{detection.bbox[1]}]
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 軌跡預測 */}
      {metadata.ar_paths && metadata.ar_paths.length > 0 && (
        <div className="card">
          <h3 className="card-title">軌跡預測</h3>
          <div className="ar-paths">
            {metadata.ar_paths.map((path, index) => (
              <div key={index} className="ar-path-item">
                <span className="path-label">預測路徑 #{index + 1}:</span>
                <span className="path-points">{path.length} 個點</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MetadataPage;
