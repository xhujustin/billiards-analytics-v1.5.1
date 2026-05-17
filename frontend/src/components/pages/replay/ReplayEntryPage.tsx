/**
 * 回放功能入口頁面
 * 
 * 提供三個主要入口：
 * 1. 個人統計分析
 * 2. 回放記錄 - 遊玩模式
 * 3. 回放記錄 - 練習模式
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
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
    const { t } = useTranslation();
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
                <h1>{t('replay.title')}</h1>
                <p>{t('replay.chooseContent')}</p>
            </div>

            <div className="replay-entry-content">
                {/* 個人統計分析 */}
                <EntryCard
                    title={t('replay.personalStats')}
                    description={t('replay.personalStatsDesc')}
                    onClick={() => handleNavigate('stats')}
                />

                {/* 回放記錄標題 */}
                <div className="section-divider">
                    <h2>{t('replay.records')}</h2>
                </div>

                {/* 遊玩模式回放 */}
                <EntryCard
                    title={t('replay.gameMode')}
                    description={t('replay.gameModeDesc')}
                    onClick={() => handleNavigate('game')}
                />

                {/* 練習模式回放 */}
                <EntryCard
                    title={t('replay.practiceMode')}
                    description={t('replay.practiceModeDesc')}
                    onClick={() => handleNavigate('practice')}
                />
            </div>
        </div>
    );
};

export default ReplayEntryPage;
