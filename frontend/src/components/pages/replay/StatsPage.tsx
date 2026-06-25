/**
 * 玩家個人統計頁面
 *
 * 桌面端產品化數據頁：整合單桿 analytics、進攻分析、母球控制、練習紀錄與既有對戰統計。
 */

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
import './StatsPage.css';

type AnalyticsRange = 'today' | 'week' | 'month' | 'year';
type StatsSection = 'battle' | 'overview' | 'offense' | 'cue' | 'practice';

interface PlayerDetailStats {
    name: string;
    total_games: number;
    total_wins: number;
    win_rate: number;
    recent_games?: any[];
    total_practice_sessions?: number;
    total_practice_seconds?: number;
    recent_practice?: Array<{
        game_id: string;
        practice_type: string;
        duration_seconds: number;
        date: string;
    }>;
}

interface OverviewPayload {
    has_data: boolean;
    today_shots: number;
    performance_score: number | null;
    pocket_rate: number | null;
    mistake_rate: number | null;
    most_common_mistake: { type: string; label: string; count: number };
    best_streak: number;
    scratch_count: number;
    cue_control_rate: number | null;
    cue_control_score: number | null;
    average_cue_landing_error_px: number | null;
    next_ball_good_rate: number | null;
    training_completion_rate: number | null;
    confidence: 'empty' | 'partial' | 'complete';
}

interface RateBucket {
    bucket: string;
    shots: number;
    made: number;
    rate: number | null;
}

interface CountBucket {
    type: string;
    label?: string;
    count: number;
}

interface OffensePayload {
    has_data: boolean;
    distance_buckets: RateBucket[];
    difficulty_buckets: RateBucket[];
    thickness: CountBucket[];
    mistakes: CountBucket[];
}

interface StatsPageProps {
    playerName: string;
    onBack?: () => void;
}

const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';

const rangeLabels: Record<AnalyticsRange, string> = {
    today: '今日',
    week: '近 7 天',
    month: '近 30 天',
    year: '近一年',
};

const bucketLabels: Record<string, string> = {
    near: '近球',
    mid: '中距離',
    far: '遠球',
    easy: '簡單球',
    medium: '中等球',
    hard: '困難球',
    too_thick: '打厚',
    too_thin: '打薄',
    on_line: '準線',
    unknown: '未知',
};

const formatRate = (value: number | null | undefined) =>
    typeof value === 'number' ? `${Math.round(value * 100)}%` : '-';

const formatValue = (value: number | null | undefined, suffix = '') =>
    typeof value === 'number' ? `${value}${suffix}` : '-';

const formatDurationText = (seconds: number | null | undefined) => {
    const total = Math.max(0, Math.round(Number(seconds || 0)));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (hours > 0) return `${hours} 小時 ${minutes} 分`;
    return `${minutes} 分`;
};

const clampPercent = (value: number | null | undefined) =>
    typeof value === 'number' ? Math.max(0, Math.min(100, value)) : 0;

const StatsPage: React.FC<StatsPageProps> = ({ playerName, onBack }) => {
    const { t, i18n } = useTranslation();
    const [playerStats, setPlayerStats] = useState<PlayerDetailStats | null>(null);
    const [overview, setOverview] = useState<OverviewPayload | null>(null);
    const [offense, setOffense] = useState<OffensePayload | null>(null);
    const [range, setRange] = useState<AnalyticsRange>('today');
    const [activeSection, setActiveSection] = useState<StatsSection>('overview');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchStats = async () => {
            setLoading(true);
            setError(null);
            try {
                const playerParam = encodeURIComponent(playerName);
                const [playerResponse, overviewResponse, offenseResponse] = await Promise.all([
                    fetch(`${apiBaseUrl}/api/stats/player/${playerParam}`),
                    fetch(`${apiBaseUrl}/api/analytics/overview?player=${playerParam}&range=${range}`),
                    fetch(`${apiBaseUrl}/api/analytics/offense?player=${playerParam}&range=${range}`),
                ]);

                if (!playerResponse.ok || !overviewResponse.ok || !offenseResponse.ok) {
                    throw new Error('analytics api failed');
                }

                const [playerData, overviewData, offenseData] = await Promise.all([
                    playerResponse.json(),
                    overviewResponse.json(),
                    offenseResponse.json(),
                ]);

                if (!cancelled) {
                    setPlayerStats(playerData);
                    setOverview(overviewData);
                    setOffense(offenseData);
                }
            } catch (fetchError) {
                console.error('Failed to fetch analytics:', fetchError);
                if (!cancelled) {
                    setError('無法讀取分析資料，請確認後端服務已啟動。');
                    setPlayerStats(null);
                    setOverview(null);
                    setOffense(null);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchStats();
        return () => {
            cancelled = true;
        };
    }, [playerName, range]);

    const sectionTabs: Array<{ key: StatsSection; label: string }> = [
        { key: 'overview', label: '總覽' },
        { key: 'battle', label: t('replay.battleStats') },
        { key: 'offense', label: '進攻分析' },
        { key: 'cue', label: '母球控制' },
        { key: 'practice', label: t('replay.recentPractice') },
    ];
    const shotCountLabel = `${rangeLabels[range]}出手數`;

    return (
        <div className="stats-page friend-match-page analytics-page">
            <div className="friend-match-panel stats-panel">
                {onBack ? (
                    <header className="friend-match-header stats-header">
                        <button className="friend-back-button" type="button" onClick={onBack} aria-label={t('common.back')}>
                            ←
                        </button>
                    </header>
                ) : null}

                <nav className="stats-view-toolbar" aria-label="統計分類">
                    <div className="stats-view-tabs" role="tablist">
                        {sectionTabs.map((section) => (
                            <button
                                key={section.key}
                                type="button"
                                role="tab"
                                className={activeSection === section.key ? 'active' : ''}
                                aria-selected={activeSection === section.key}
                                onClick={() => setActiveSection(section.key)}
                            >
                                {section.label}
                            </button>
                        ))}
                    </div>
                    <select
                        className="stats-range-select"
                        value={range}
                        onChange={(event) => setRange(event.target.value as AnalyticsRange)}
                        aria-label={t('replay.timeRange')}
                    >
                        {(Object.keys(rangeLabels) as AnalyticsRange[]).map((item) => (
                            <option key={item} value={item}>{rangeLabels[item]}</option>
                        ))}
                    </select>
                </nav>

                {loading ? <div className="loading">{t('replay.loading')}</div> : null}
                {error ? <div className="empty-state">{error}</div> : null}

                {!loading && !error && activeSection === 'battle' && playerStats ? (
                    <section className="stats-view-section" role="tabpanel">
                        <div className="friend-status-grid stats-cards">
                            <MetricCard label={t('replay.totalGames')} value={`${playerStats.total_games}`} />
                            <MetricCard label={t('replay.wins')} value={`${playerStats.total_wins}`} />
                            <MetricCard label={t('replay.winRate')} value={`${(playerStats.win_rate * 100).toFixed(1)}%`} />
                            <MetricCard label={t('replay.totalPractice')} value={`${playerStats.total_practice_sessions || 0}`} />
                            <MetricCard label="練習總時長" value={formatDurationText(playerStats.total_practice_seconds)} />
                        </div>

                        {playerStats.recent_games && playerStats.recent_games.length > 0 ? (
                            <div className="recent-practice">
                                <h3>最近對戰</h3>
                                <div className="practice-list">
                                    {playerStats.recent_games.slice(0, 5).map((game, index) => (
                                        <article key={`${game.game_id}-${index}`} className="practice-item">
                                            <span className="practice-type">{game.result === 'win' ? '勝' : game.result === 'loss' ? '敗' : '和'}</span>
                                            <div className="practice-duration">
                                                <span className="duration-label">對手:</span>
                                                <span className="duration-value">{game.opponent || '未知'}</span>
                                            </div>
                                            <span className="practice-date">{game.score || '-'}</span>
                                        </article>
                                    ))}
                                </div>
                            </div>
                        ) : null}
                    </section>
                ) : null}

                {!loading && !error && activeSection !== 'battle' && activeSection !== 'practice' && overview && !overview.has_data ? (
                    <section className="stats-view-section" role="tabpanel">
                        <p className="analytics-empty-copy">
                            尚未累積可用於此分類的真實出桿資料。
                        </p>
                    </section>
                ) : null}

                {!loading && !error && activeSection === 'overview' && overview?.has_data ? (
                    <section className="stats-view-section" role="tabpanel">
                        <div className="friend-status-grid stats-cards analytics-card-grid">
                            <MetricCard label="表現分數" value={formatValue(overview.performance_score, ' 分')} />
                            <MetricCard label="進球率" value={formatRate(overview.pocket_rate)} />
                            <MetricCard label="最常失誤" value={overview.most_common_mistake?.label || '-'} />
                            <MetricCard label={shotCountLabel} value={`${overview.today_shots} 桿`} />
                            <MetricCard label="最佳連進" value={`${overview.best_streak} 球`} />
                            <MetricCard label="訓練完成率" value={formatRate(overview.training_completion_rate)} progress={(overview.training_completion_rate ?? 0) * 100} />
                        </div>
                    </section>
                ) : null}

                {!loading && !error && activeSection === 'offense' && overview?.has_data ? (
                    <section className="stats-view-section" role="tabpanel">
                        <div className="analytics-data-stack">
                            <BucketPanel title="近 / 中 / 遠進球率" buckets={offense?.distance_buckets || []} />
                            <BucketPanel title="簡單 / 中等 / 困難成功率" buckets={offense?.difficulty_buckets || []} />
                            <CountPanel title="打厚 / 打薄" items={offense?.thickness || []} />
                            <CountPanel title="失誤方向" items={offense?.mistakes || []} />
                        </div>
                    </section>
                ) : null}

                {!loading && !error && activeSection === 'cue' && overview?.has_data ? (
                    <section className="stats-view-section" role="tabpanel">
                        <div className="friend-status-grid stats-cards analytics-card-grid">
                            <MetricCard label="走位成功率" value={formatRate(overview.cue_control_rate)} progress={(overview.cue_control_rate ?? 0) * 100} />
                            <MetricCard label="停點偏差" value={formatValue(overview.average_cue_landing_error_px, ' px')} progress={overview.average_cue_landing_error_px ? Math.max(0, 100 - overview.average_cue_landing_error_px) : 0} />
                            <MetricCard label="洗袋次數" value={`${overview.scratch_count} 次`} progress={Math.min(100, overview.scratch_count * 20)} tone="danger" />
                            <MetricCard label="下一球好打比例" value={formatRate(overview.next_ball_good_rate)} progress={(overview.next_ball_good_rate ?? 0) * 100} />
                            <MetricCard label={shotCountLabel} value={`${overview.today_shots} 桿`} />
                        </div>
                    </section>
                ) : null}

                {!loading && !error && activeSection === 'practice' && playerStats ? (
                    <section className="stats-view-section" role="tabpanel">
                        <div className="recent-practice">
                            <div className="practice-list">
                                {(playerStats.recent_practice || []).map((practice, index) => (
                                    <article key={`${practice.game_id}-${index}`} className="practice-item">
                                        <span className="practice-type">{practice.practice_type}</span>
                                        <div className="practice-duration">
                                            <span className="duration-label">{t('replay.practiceDuration')}:</span>
                                            <span className="duration-value">
                                                {Math.floor(practice.duration_seconds / 60)}:{String(Math.floor(practice.duration_seconds % 60)).padStart(2, '0')}
                                            </span>
                                        </div>
                                        <span className="practice-date">
                                            {new Date(practice.date).toLocaleDateString(i18n.language)}
                                        </span>
                                    </article>
                                ))}
                                {!playerStats.recent_practice?.length ? <p className="analytics-empty-copy">尚無練習紀錄。</p> : null}
                            </div>
                        </div>
                    </section>
                ) : null}
            </div>
        </div>
    );
};

function MetricCard({
    label,
    value,
    progress,
    tone = 'primary',
}: {
    label: string;
    value: string;
    progress?: number | null;
    tone?: 'primary' | 'success' | 'danger' | 'warning';
}) {
    const hasProgress = typeof progress === 'number';

    return (
        <div className={`friend-status-pill stat-card analytics-metric-card ${hasProgress ? 'has-progress' : 'without-progress'} tone-${tone}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            {hasProgress ? (
                <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${clampPercent(progress)}%` }} />
                </div>
            ) : null}
        </div>
    );
}

function BucketPanel({ title, buckets }: { title: string; buckets: RateBucket[] }) {
    return (
        <article className="analytics-panel">
            <h3>{title}</h3>
            <div className="analytics-panel-list">
                {buckets.map((bucket) => (
                    <div key={bucket.bucket} className="analytics-row">
                        <span>{bucketLabels[bucket.bucket] || bucket.bucket}</span>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${clampPercent((bucket.rate ?? 0) * 100)}%` }} />
                        </div>
                        <strong>{formatRate(bucket.rate)} ({bucket.made}/{bucket.shots})</strong>
                    </div>
                ))}
                {buckets.length === 0 ? <p>尚無資料</p> : null}
            </div>
        </article>
    );
}

function CountPanel({ title, items }: { title: string; items: CountBucket[] }) {
    const total = Math.max(1, items.reduce((sum, item) => sum + item.count, 0));

    return (
        <article className="analytics-panel">
            <h3>{title}</h3>
            <div className="analytics-panel-list">
                {items.length > 0 ? items.map((item) => (
                    <div key={item.type} className="analytics-row">
                        <span>{item.label || bucketLabels[item.type] || item.type}</span>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${clampPercent((item.count / total) * 100)}%` }} />
                        </div>
                        <strong>{item.count} 次</strong>
                    </div>
                )) : <p>目前沒有明顯資料</p>}
            </div>
        </article>
    );
}

export default StatsPage;
