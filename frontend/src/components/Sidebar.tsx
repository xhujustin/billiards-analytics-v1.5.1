/**
 * Sidebar Component - 側邊欄選單
 * 提供頁面導航
 * v1.5 移除 Session 和 Metadata 選單（已整合到設定頁面）
 */

import React from 'react';
import './Sidebar.css';

export type PageType = 'practice' | 'game' | 'stream' | 'settings' | 'replay' | 'calibration';

interface SidebarProps {
  currentPage: PageType;
  onPageChange: (page: PageType) => void;
}

interface MenuItem {
  id: PageType;
  icon: string;
  label: string;
}

const menuItems: MenuItem[] = [
  { id: 'stream', icon: '', label: '即時影像' },
  { id: 'replay', icon: '', label: '回放功能' },
  { id: 'practice', icon: '', label: '練習模式' },
  { id: 'game', icon: '', label: '遊玩模式' },
  { id: 'settings', icon: '', label: '設定' },
];

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onPageChange }) => {
  return (
    <div className="sidebar">
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onPageChange(item.id)}
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span className="sidebar-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
