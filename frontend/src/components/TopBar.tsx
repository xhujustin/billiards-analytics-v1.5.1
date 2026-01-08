/**
 * TopBar Component - 頂部導航欄
 * 包含 Logo、標題和 YOLO 控制按鈕
 */

import React, { useState } from 'react';
import './TopBar.css';

interface TopBarProps {
  isAnalyzing: boolean;
  onToggleAnalysis: () => Promise<void>;
}

export const TopBar: React.FC<TopBarProps> = ({ isAnalyzing, onToggleAnalysis }) => {
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      await onToggleAnalysis();
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="top-bar">
      <div className="top-bar-left">
        <div className="logo">🎱</div>
        <h1 className="title">撞球分析系統 v1.5</h1>
      </div>

      <div className="top-bar-right">
        <button
          className="btn btn-start"
          onClick={handleToggle}
          disabled={isToggling || isAnalyzing}
        >
          {isToggling && !isAnalyzing ? '⏳ 啟動中...' : '🟢 啟動辨識'}
        </button>
        <button
          className="btn btn-stop"
          onClick={handleToggle}
          disabled={isToggling || !isAnalyzing}
        >
          {isToggling && isAnalyzing ? '⏳ 停止中...' : '🔴 停止辨識'}
        </button>
      </div>
    </div>
  );
};

export default TopBar;
