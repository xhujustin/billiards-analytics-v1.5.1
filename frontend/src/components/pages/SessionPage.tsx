/**
 * SessionPage Component - Session 資訊頁面
 */

import React from 'react';
import type { Session } from '../../sdk/types';
import './SessionPage.css';

interface SessionPageProps {
  session: Session | null;
}

export const SessionPage: React.FC<SessionPageProps> = ({ session }) => {
  const copySessionId = () => {
    if (session?.session_id) {
      navigator.clipboard.writeText(session.session_id);
      alert('Session ID 已複製到剪貼簿');
    }
  };

  if (!session) {
    return (
      <div className="session-page">
        <h2 className="page-title">📊 Session 資訊</h2>
        <div className="card">
          <p className="no-data">正在載入 Session 資訊...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="session-page">
      <h2 className="page-title">📊 Session 資訊</h2>

      {/* Session 詳細資訊 */}
      <div className="card">
        <h3 className="card-title">Session 詳細資訊</h3>
        <div className="session-details">
          <div className="detail-row">
            <span className="detail-label">Session ID:</span>
            <code className="detail-value">{session.session_id}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Stream ID:</span>
            <code className="detail-value">{session.stream_id}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Role:</span>
            <code className="detail-value">{session.role}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">狀態:</span>
            <span className="detail-value status-active">🟢 Active</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">過期時間:</span>
            <span className="detail-value">
              {new Date(session.expires_at).toLocaleString()}
            </span>
          </div>

          <div className="session-actions">
            <button className="btn btn-secondary" onClick={copySessionId}>
              📋 複製 Session ID
            </button>
          </div>
        </div>
      </div>

      {/* 權限資訊 */}
      <div className="card">
        <h3 className="card-title">權限資訊</h3>
        <div className="permissions">
          {session.permission_flags && session.permission_flags.length > 0 ? (
            session.permission_flags.map((permission) => (
              <div key={permission} className="permission-item">
                <span className="permission-icon">✓</span>
                <span className="permission-name">{permission}</span>
                <span className="permission-desc">
                  {getPermissionDescription(permission)}
                </span>
              </div>
            ))
          ) : (
            <p className="no-data">無權限資訊</p>
          )}
        </div>
      </div>
    </div>
  );
};

function getPermissionDescription(permission: string): string {
  const descriptions: Record<string, string> = {
    view: '查看即時影像',
    calibrate: '校準控制',
    replay: '回放控制',
    score_control: '計分控制',
  };
  return descriptions[permission] || permission;
}

export default SessionPage;
