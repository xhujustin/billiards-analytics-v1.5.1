/**
 * Session Manager（v1.5）
 * 管理 session 生命週期、自動續期
 */

import { Role } from './types';
import type { Session, SessionRenewResponse } from './types';

export class SessionManager {
  private apiBaseUrl: string;
  private currentSession: Session | null = null;
  private renewTimer: NodeJS.Timeout | null = null;
  private autoRenew: boolean;
  private renewWindowRatio: number;
  private minRenewWindow: number;

  constructor(
    apiBaseUrl: string,
    config: {
      autoRenew?: boolean;
      renewWindowRatio?: number;
      minRenewWindow?: number;
    } = {}
  ) {
    this.apiBaseUrl = apiBaseUrl;
    this.autoRenew = config.autoRenew ?? true;
    this.renewWindowRatio = config.renewWindowRatio ?? 0.2;
    this.minRenewWindow = config.minRenewWindow ?? 300000; // 5min
  }

  /**
   * 創建新 session
   */
  async createSession(
    streamId: string,
    role: Role = Role.OPERATOR,
    clientInfo: any = {}
  ): Promise<Session> {
    const response = await fetch(`${this.apiBaseUrl}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stream_id: streamId,
        role_requested: role,
        client_info: {
          ...clientInfo,
          user_agent: navigator.userAgent,
          timestamp: Date.now(),
        },
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.statusText}`);
    }

    const session: Session = await response.json();
    this.currentSession = session;

    // 保存到 localStorage
    localStorage.setItem('billiards_session_id', session.session_id);
    localStorage.setItem('billiards_session', JSON.stringify(session));

    // 啟動自動續期
    if (this.autoRenew) {
      this.scheduleRenew(session);
    }

    console.log('✅ Session created:', session.session_id);
    return session;
  }

  /**
   * 從 localStorage 恢復 session
   */
  async restoreSession(): Promise<Session | null> {
    const sessionId = localStorage.getItem('billiards_session_id');
    const sessionData = localStorage.getItem('billiards_session');

    if (!sessionId || !sessionData) {
      return null;
    }

    try {
      const session: Session = JSON.parse(sessionData);

      // 檢查是否過期
      if (Date.now() > session.expires_at) {
        console.warn('⚠️ Stored session expired, creating new one');
        this.clearSession();
        return null;
      }

      // 嘗試續期
      const renewed = await this.renewSession(sessionId);
      if (renewed) {
        this.currentSession = session;
        this.scheduleRenew(session);
        console.log('✅ Session restored and renewed:', sessionId);
        return session;
      }

      return null;
    } catch (error) {
      console.error('Failed to restore session:', error);
      this.clearSession();
      return null;
    }
  }

  /**
   * 續期 session
   */
  async renewSession(sessionId: string): Promise<boolean> {
    try {
      const response = await fetch(
        `${this.apiBaseUrl}/api/sessions/${sessionId}/renew`,
        {
          method: 'POST',
        }
      );

      if (!response.ok) {
        return false;
      }

      const result: SessionRenewResponse = await response.json();

      // 更新 localStorage
      if (this.currentSession) {
        this.currentSession.expires_at = result.expires_at;
        localStorage.setItem(
          'billiards_session',
          JSON.stringify(this.currentSession)
        );
      }

      console.log('🔄 Session renewed, new expiry:', new Date(result.expires_at));
      return true;
    } catch (error) {
      console.error('Failed to renew session:', error);
      return false;
    }
  }

  /**
   * 刪除 session
   */
  async deleteSession(sessionId?: string): Promise<void> {
    const id = sessionId || this.currentSession?.session_id;
    if (!id) return;

    try {
      await fetch(`${this.apiBaseUrl}/api/sessions/${id}`, {
        method: 'DELETE',
      });
      console.log('🗑️ Session deleted:', id);
    } catch (error) {
      console.error('Failed to delete session:', error);
    } finally {
      this.clearSession();
    }
  }

  /**
   * 切換 stream
   */
  async switchStream(newStreamId: string): Promise<boolean> {
    if (!this.currentSession) return false;

    try {
      const response = await fetch(
        `${this.apiBaseUrl}/api/sessions/${this.currentSession.session_id}/switch_stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stream_id: newStreamId }),
        }
      );

      if (!response.ok) return false;

      const result = await response.json();
      this.currentSession.stream_id = result.new_stream_id;
      this.currentSession.burnin_url = result.new_burnin_url;

      // 更新 localStorage
      localStorage.setItem(
        'billiards_session',
        JSON.stringify(this.currentSession)
      );

      console.log('🔀 Stream switched to:', newStreamId);
      return true;
    } catch (error) {
      console.error('Failed to switch stream:', error);
      return false;
    }
  }

  /**
   * 獲取當前 session
   */
  getCurrentSession(): Session | null {
    return this.currentSession;
  }

  /**
   * 清理 session
   */
  private clearSession(): void {
    if (this.renewTimer) {
      clearTimeout(this.renewTimer);
      this.renewTimer = null;
    }
    this.currentSession = null;
    localStorage.removeItem('billiards_session_id');
    localStorage.removeItem('billiards_session');
  }

  /**
   * 調度自動續期
   */
  private scheduleRenew(session: Session): void {
    if (this.renewTimer) {
      clearTimeout(this.renewTimer);
    }

    const ttl = session.expires_at - Date.now();
    
    // v1.5 定案續期視窗公式：min(ttl * renewWindowRatio, minRenewWindow)
    // 避免短 session 特例（例如 3 分鐘 session 不會要求提前 5 分鐘續期）
    const renewWindow = Math.min(ttl * this.renewWindowRatio, this.minRenewWindow);
    const renewTime = ttl - renewWindow;

    if (renewTime > 0) {
      this.renewTimer = setTimeout(async () => {
        const success = await this.renewSession(session.session_id);
        if (success && this.currentSession) {
          this.scheduleRenew(this.currentSession);
        } else {
          console.warn('⚠️ Failed to renew session, creating new one...');
          // Fallback: 創建新 session
          try {
            await this.createSession(session.stream_id, session.role as Role);
          } catch (error) {
            console.error('Failed to create fallback session:', error);
          }
        }
      }, renewTime);

      console.log(
        `⏰ Scheduled auto-renew in ${Math.round(renewTime / 1000)}s (window: ${Math.round(renewWindow / 1000)}s)`
      );
    }
  }

  /**
   * 銷毀管理器
   */
  destroy(): void {
    this.clearSession();
  }
}
