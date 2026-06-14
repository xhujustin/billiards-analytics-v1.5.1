/**
 * 玩家個人統計頁面
 *
 * 桌面端產品化數據頁：整合單桿 analytics、進攻分析、母球控制、練習紀錄與既有對戰統計。
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../GamePage.css';
import './StatsPage.css';

type AnalyticsRange = 'today' | 'week' | 'month' | 'year';
type TrendBucket = 'day' | 'week' | 'month' | 'year';

interface PlayerDetailStats {
    name: string;
    total_games: number;
    total_wins: number;
    win_rate: number;
    recent_games?: any[];
    total_practice_sessions?: number;
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
    ai_advice: string;
    recommended_practice: string;
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

interface TrendPayload {
    has_data: boolean;
    points: Array<{
        label: string;
        performance_score: number | null;
        pocket_rate: number | null;
        mistake_rate: number | null;
        cue_control_score: number | null;
        shot_count: number;
    }>;
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

const trendLabels: Record<TrendBucket, string> = {
    day: '日',
    week: '週',
    month: '月',
    year: '年',
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
    typeof value === 'number' ? `${Math.round(value * 100)}%` : '資料累積中';

const formatValue = (value: number | null | undefined, suffix = '') =>
    typeof value === 'number' ? `${value}${suffix}` : '資料累積中';

const clampPercent = (value: number | null | undefined) =>
    typeof value === 'number' ? Math.max(0, Math.min(100, value)) : 0;

const trendSeries = [
    { key: 'score', label: '表現分數', color: '#4f46e5' },
    { key: 'pocket', label: '進球率', color: '#22c55e' },
    { key: 'mistake', label: '失誤率', color: '#ef4444' },
    { key: 'cue', label: '母球控制', color: '#06b6d4' },
] as const;

const StatsPage: React.FC<StatsPageProps> = ({ playerName, onBack }) => {
    const { t, i18n } = useTranslation();
    const [playerStats, setPlayerStats] = useState<PlayerDetailStats | null>(null);
    const [overview, setOverview] = useState<OverviewPayload | null>(null);
    const [offense, setOffense] = useState<OffensePayload | null>(null);
    const [trends, setTrends] = useState<TrendPayload | null>(null);
    const [range, setRange] = useState<AnalyticsRange>('today');
    const [trendBucket, setTrendBucket] = useState<TrendBucket>('day');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchStats = async () => {
            setLoading(true);
            setError(null);
            try {
                const playerParam = encodeURIComponent(playerName);
                const [playerResponse, overviewResponse, offenseResponse, trendsResponse] = await Promise.all([
                    fetch(`${apiBaseUrl}/api/stats/player/${playerParam}`),
                    fetch(`${apiBaseUrl}/api/analytics/overview?player=${playerParam}&range=${range}`),
                    fetch(`${apiBaseUrl}/api/analytics/offense?player=${playerParam}&range=${range}`),
                    fetch(`${apiBaseUrl}/api/analytics/trends?player=${playerParam}&bucket=${trendBucket}`),
                ]);

                if (!playerResponse.ok || !overviewResponse.ok || !offenseResponse.ok || !trendsResponse.ok) {
                    throw new Error('analytics api failed');
                }

                const [playerData, overviewData, offenseData, trendsData] = await Promise.all([
                    playerResponse.json(),
                    overviewResponse.json(),
                    offenseResponse.json(),
                    trendsResponse.json(),
                ]);

                if (!cancelled) {
                    setPlayerStats(playerData);
                    setOverview(overviewData);
                    setOffense(offenseData);
                    setTrends(trendsData);
                }
            } catch (fetchError) {
                console.error('Failed to fetch analytics:', fetchError);
                if (!cancelled) {
                    setError('無法讀取分析資料，請確認後端服務已啟動。');
                    setPlayerStats(null);
                    setOverview(null);
                    setOffense(null);
                    setTrends(null);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchStats();
        return () => {
            cancelled = true;
        };
    }, [playerName, range, trendBucket]);

    const trendPoints = useMemo(
        () => (trends?.points || []).map((point) => ({
            label: point.label,
            score: point.performance_score ?? 0,
            pocket: typeof point.pocket_rate === 'number' ? Math.round(point.pocket_rate * 100) : 0,
            mistake: typeof point.mistake_rate === 'number' ? Math.round(point.mistake_rate * 100) : 0,
            cue: point.cue_control_score ?? 0,
            shots: point.shot_count,
        })),
        [trends],
    );

    return (
        <div className="stats-page friend-match-page analytics-page">
            <div className="friend-match-panel stats-panel">
                <header className="friend-match-header stats-header">
                    {onBack && (
                        <button className="friend-back-button" type="button" onClick={onBack} aria-label={t('common.back')}>
                            ←
                        </button>
                    )}
                    <div>
                        <h1>{t('replay.statsTitle', { player: playerName })}</h1>
                        <p>查看真實出桿數據、進攻弱項、母球控制、練習紀錄與趨勢。</p>
                    </div>
                </header>

                <section className="friend-setup-section time-range-selector">
                    <div className="friend-section-title">
                        <span>1</span>
                        <h2>{t('replay.timeRange')}</h2>
                    </div>
                    <div className="friend-segment-row stats-range-row">
                        {(Object.keys(rangeLabels) as AnalyticsRange[]).map((item) => (
                            <button
                                key={item}
                                type="button"
                                className={range === item ? 'active' : ''}
                                onClick={() => setRange(item)}
                            >
                                {rangeLabels[item]}
                            </button>
                        ))}
                    </div>
                </section>

                {loading ? <div className="loading">{t('replay.loading')}</div> : null}
                {error ? <div className="empty-state">{error}</div> : null}

                {!loading && !error && overview && !overview.has_data ? (
                    <section className="friend-setup-section stats-section">
                        <div className="friend-section-title">
                            <span>2</span>
                            <h2>資料累積中</h2>
                        </div>
                        <p className="analytics-empty-copy">
                            目前沒有符合範圍的真實出桿資料。完成練習或遊戲出桿後，這裡會顯示表現分數、進球率、失誤與 AI 建議。
                        </p>
                    </section>
                ) : null}

                {!loading && !error && overview ? (
                    <>
                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title">
                                <span>2</span>
                                <h2>今日總覽</h2>
                            </div>
                            <div className="friend-status-grid stats-cards analytics-card-grid">
                                <MetricCard label="表現分數" value={formatValue(overview.performance_score, ' 分')} progress={overview.performance_score} />
                                <MetricCard label="進球率" value={formatRate(overview.pocket_rate)} progress={(overview.pocket_rate ?? 0) * 100} tone="success" />
                                <MetricCard label="最常失誤" value={overview.most_common_mistake?.label || '資料累積中'} progress={(overview.mistake_rate ?? 0) * 100} tone="warning" />
                                <MetricCard label="AI 建議" value={overview.recommended_practice || '資料累積中'} />
                            </div>
                            <article className="analytics-advice">
                                <span>{overview.confidence === 'complete' ? '資料完整' : overview.confidence === 'partial' ? '資料累積中' : '尚無資料'}</span>
                                <p>{overview.ai_advice}</p>
                            </article>
                        </section>

                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title">
                                <span>3</span>
                                <h2>進攻分析</h2>
                            </div>
                            <div className="analytics-two-column">
                                <BucketPanel title="近 / 中 / 遠進球率" buckets={offense?.distance_buckets || []} />
                                <BucketPanel title="簡單 / 中等 / 困難成功率" buckets={offense?.difficulty_buckets || []} />
                            </div>
                            <div className="analytics-two-column">
                                <CountPanel title="打厚 / 打薄" items={offense?.thickness || []} />
                                <CountPanel title="失誤方向" items={offense?.mistakes || []} />
                            </div>
                        </section>

                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title">
                                <span>4</span>
                                <h2>母球控制與練習紀錄</h2>
                            </div>
                            <div className="friend-status-grid stats-cards analytics-card-grid">
                                <MetricCard label="走位成功率" value={formatRate(overview.cue_control_rate)} progress={(overview.cue_control_rate ?? 0) * 100} />
                                <MetricCard label="停點偏差" value={formatValue(overview.average_cue_landing_error_px, ' px')} progress={overview.average_cue_landing_error_px ? Math.max(0, 100 - overview.average_cue_landing_error_px) : 0} />
                                <MetricCard label="洗袋次數" value={`${overview.scratch_count} 次`} progress={Math.min(100, overview.scratch_count * 20)} tone="danger" />
                                <MetricCard label="下一球好打比例" value={formatRate(overview.next_ball_good_rate)} progress={(overview.next_ball_good_rate ?? 0) * 100} />
                                <MetricCard label="今日出手數" value={`${overview.today_shots} 桿`} />
                                <MetricCard label="最佳連進" value={`${overview.best_streak} 球`} />
                                <MetricCard label="訓練完成率" value={formatRate(overview.training_completion_rate)} progress={(overview.training_completion_rate ?? 0) * 100} />
                                <MetricCard label="推薦練習" value={overview.recommended_practice || '資料累積中'} />
                            </div>
                        </section>

                        <section className="friend-setup-section stats-section">
                            <div className="friend-section-title analytics-trend-title">
                                <span>5</span>
                                <h2>趨勢</h2>
                                <div className="friend-segment-row analytics-trend-switch">
                                    {(Object.keys(trendLabels) as TrendBucket[]).map((item) => (
                                        <button
                                            key={item}
                                            type="button"
                                            className={trendBucket === item ? 'active' : ''}
                                            onClick={() => setTrendBucket(item)}
                                        >
                                            {trendLabels[item]}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            {trendPoints.length > 0 ? (
                                <div className="analytics-chart">
                                    <TrendChart points={trendPoints} />
                                </div>
                            ) : (
                                <div className="empty-state">尚無趨勢資料</div>
                            )}
                        </section>
                    </>
                ) : null}

                {!loading && !error && playerStats ? (
                    <section className="friend-setup-section stats-section">
                        <div className="friend-section-title">
                            <span>6</span>
                            <h2>{t('replay.battleStats')}</h2>
                        </div>
                        <div className="friend-status-grid stats-cards">
                            <MetricCard label={t('replay.totalGames')} value={`${playerStats.total_games}`} />
                            <MetricCard label={t('replay.wins')} value={`${playerStats.total_wins}`} />
                            <MetricCard label={t('replay.winRate')} value={`${(playerStats.win_rate * 100).toFixed(1)}%`} progress={playerStats.win_rate * 100} />
                            <MetricCard label={t('replay.totalPractice')} value={`${playerStats.total_practice_sessions || 0}`} />
                        </div>

                        {playerStats.recent_practice && playerStats.recent_practice.length > 0 && (
                            <div className="recent-practice">
                                <h3>{t('replay.recentPractice')}</h3>
                                <div className="practice-list">
                                    {playerStats.recent_practice.map((practice, index) => (
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
                                </div>
                            </div>
                        )}
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
    return (
        <div className={`friend-status-pill stat-card analytics-metric-card tone-${tone}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            {typeof progress === 'number' ? (
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
                {buckets.length === 0 ? <p>資料累積中</p> : null}
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

function TrendChart({
    points,
}: {
    points: Array<{ label: string; score: number; pocket: number; mistake: number; cue: number; shots: number }>;
}) {
    const width = 720;
    const height = 220;
    const padding = { top: 18, right: 18, bottom: 36, left: 28 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const xFor = (index: number) =>
        padding.left + (points.length <= 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
    const yFor = (value: number) => padding.top + chartHeight - (clampPercent(value) / 100) * chartHeight;
    const pathFor = (key: (typeof trendSeries)[number]['key']) =>
        points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xFor(index).toFixed(1)} ${yFor(point[key]).toFixed(1)}`).join(' ');
    const labelIndexes = points.length > 8
        ? points.map((_, index) => index).filter((index) => index === 0 || index === points.length - 1 || index % Math.ceil(points.length / 6) === 0)
        : points.map((_, index) => index);

    return (
        <div className="analytics-chart-inner">
            <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="分析趨勢圖">
                {[0, 25, 50, 75, 100].map((tick) => (
                    <g key={tick}>
                        <line
                            x1={padding.left}
                            x2={width - padding.right}
                            y1={yFor(tick)}
                            y2={yFor(tick)}
                            className="analytics-chart-grid"
                        />
                        <text x={8} y={yFor(tick) + 4} className="analytics-chart-axis">{tick}</text>
                    </g>
                ))}
                {trendSeries.map((series) => (
                    <path
                        key={series.key}
                        d={pathFor(series.key)}
                        fill="none"
                        stroke={series.color}
                        strokeWidth={series.key === 'score' ? 3 : 2.4}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    />
                ))}
                {labelIndexes.map((index) => (
                    <text
                        key={`${points[index].label}-${index}`}
                        x={xFor(index)}
                        y={height - 12}
                        textAnchor="middle"
                        className="analytics-chart-axis"
                    >
                        {points[index].label}
                    </text>
                ))}
            </svg>
            <div className="analytics-chart-legend">
                {trendSeries.map((series) => (
                    <span key={series.key}>
                        <i style={{ background: series.color }} />
                        {series.label}
                    </span>
                ))}
            </div>
        </div>
    );
}

export default StatsPage;
