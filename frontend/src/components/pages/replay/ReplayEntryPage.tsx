/**
 * 回放功能入口頁面
 * 
 * 提供三個主要入口：
 * 1. 個人統計分析
 * 2. 回放記錄 - 遊玩模式
 * 3. 回放記錄 - 練習模式
 */

import React from 'react';
import './ReplayEntryPage.css';

interface EntryCardProps {
    title: string;
    description: string;
    onClick: () => void;
}

const EntryCard: React.FC<EntryCardProps> = ({ title, description, onClick }) => {
    return (
        <div className="entry-card" onClick={onClick}>
            <div className="entry-card-content">
                <h3 className="entry-card-title">{title}</h3>
                <p className="entry-card-description">{description}</p>
            </div>
            <div className="entry-card-arrow">→</div>
        </div>
    );
};

interface ReplayEntryPageProps {
    onNavigate?: (page: 'stats' | 'game' | 'practice') => void;
}

const ReplayEntryPage: React.FC<ReplayEntryPageProps> = ({ onNavigate }) => {
    const handleNavigate = (page: 'stats' | 'game' | 'practice') => {
        if (onNavigate) {
            onNavigate(page);
        } else {
            // 預設行為：在控制台輸出（開發時使用）
            console.log(`Navigate to: ${page}`);
        }
    };

    return (
        <div className="replay-entry-page">
            <div className="replay-entry-header">
                <h1>回放功能</h1>
                <p>選擇您要查看的內容</p>
            </div>

            <div className="replay-entry-content">
                {/* 個人統計分析 */}
                <EntryCard
                    title="個人統計分析"
                    description="查看您的遊玩記錄、勝率統計和進步曲線"
                    onClick={() => handleNavigate('stats')}
                />

                {/* 回放記錄標題 */}
                <div className="section-divider">
                    <h2>回放記錄</h2>
                </div>

                {/* 遊玩模式回放 */}
                <EntryCard
                    title="遊玩模式"
                    description="查看 9 球對戰的錄影回放"
                    onClick={() => handleNavigate('game')}
                />

                {/* 練習模式回放 */}
                <EntryCard
                    title="練習模式"
                    description="查看單球練習和球型練習的錄影回放"
                    onClick={() => handleNavigate('practice')}
                />
            </div>
        </div>
    );
};

export default ReplayEntryPage;
