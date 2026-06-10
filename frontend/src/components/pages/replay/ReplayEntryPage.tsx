/**
 * 回放功能入口頁面
 * 
 * 提供兩個主要入口：
 * 1. 回放記錄 - 遊玩模式
 * 2. 回放記錄 - 練習模式
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
import './ReplayEntryPage.css';

interface EntryCardProps {
    title: string;
    description: string;
    onClick: () => void;
    className?: string;
}

const EntryCard: React.FC<EntryCardProps> = ({ title, description, onClick, className }) => {
    return (
        <button
            type="button"
            className={`entry-card replay-entry-card friend-game-type-card ${className || ''}`}
            onClick={onClick}
        >
            <div className="entry-card-content">
                <h3 className="entry-card-title">{title}</h3>
                <p className="entry-card-description">{description}</p>
            </div>
            <div className="entry-card-arrow">→</div>
        </button>
    );
};

interface ReplayEntryPageProps {
    onNavigate?: (page: 'game' | 'practice') => void;
}

const ReplayEntryPage: React.FC<ReplayEntryPageProps> = ({ onNavigate }) => {
    const { t } = useTranslation();
    const handleNavigate = (page: 'game' | 'practice') => {
        if (onNavigate) {
            onNavigate(page);
        } else {
            // 預設行為：在控制台輸出（開發時使用）
            console.log(`Navigate to: ${page}`);
        }
    };

    return (
        <div className="replay-entry-page friend-match-page">
            <div className="friend-match-panel replay-entry-panel">
                <header className="friend-match-header replay-entry-header">
                    <div>
                        <h1>{t('replay.title')}</h1>
                        <p>{t('replay.chooseContent')}</p>
                    </div>
                </header>

                <section className="friend-setup-section replay-entry-content">
                    <div className="friend-section-title">
                        <h2>{t('replay.records')}</h2>
                    </div>

                    <div className="replay-entry-grid">
                        <EntryCard
                            title={t('replay.gameMode')}
                            description={t('replay.gameModeDesc')}
                            onClick={() => handleNavigate('game')}
                        />

                        <EntryCard
                            title={t('replay.practiceMode')}
                            description={t('replay.practiceModeDesc')}
                            onClick={() => handleNavigate('practice')}
                        />
                    </div>
                </section>
            </div>
        </div>
    );
};

export default ReplayEntryPage;
