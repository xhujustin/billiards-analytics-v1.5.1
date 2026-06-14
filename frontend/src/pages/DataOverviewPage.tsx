import { useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DataSection } from '../MobilePrototypeApp';
import DropdownSelector from '../components/DropdownSelector';
import PageHeader from '../components/PageHeader';
import ProgressBar from '../components/ProgressBar';
import StatCard from '../components/StatCard';

type AnalyticsRange = 'today' | 'week' | 'month' | 'year';
type TrendBucket = 'day' | 'week' | 'month' | 'year';

interface OverviewPayload {
  has_data: boolean;
  today_shots: number;
  performance_score: number | null;
  pocket_rate: number | null;
  mistake_rate: number | null;
  most_common_mistake: { label: string; count: number };
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

const rangeLabels: Record<AnalyticsRange, string> = {
  today: '今日',
  week: '近 7 天',
  month: '近 30 天',
  year: '近一年',
};

const bucketLabels: Record<TrendBucket, string> = {
  day: '日',
  week: '週',
  month: '月',
  year: '年',
};

const formatRate = (value: number | null | undefined) => (
  typeof value === 'number' ? `${Math.round(value * 100)}%` : '資料累積中'
);

const formatNumber = (value: number | null | undefined, suffix = '') => (
  typeof value === 'number' ? `${value}${suffix}` : '資料累積中'
);

const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';

export default function DataOverviewPage({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (section: DataSection) => void;
}) {
  const [range, setRange] = useState<AnalyticsRange>('today');
  const [bucket, setBucket] = useState<TrendBucket>('day');
  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [trends, setTrends] = useState<TrendPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [overviewResponse, trendsResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/api/analytics/overview?range=${range}`),
          fetch(`${apiBaseUrl}/api/analytics/trends?bucket=${bucket}`),
        ]);
        if (!overviewResponse.ok || !trendsResponse.ok) {
          throw new Error('analytics api failed');
        }
        const [overviewData, trendsData] = await Promise.all([
          overviewResponse.json(),
          trendsResponse.json(),
        ]);
        if (!cancelled) {
          setOverview(overviewData);
          setTrends(trendsData);
        }
      } catch {
        if (!cancelled) {
          setError('無法讀取數據，請確認後端服務已啟動。');
          setOverview(null);
          setTrends(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [bucket, range]);

  const trendPoints = (trends?.points || []).map((point) => ({
    label: point.label,
    score: point.performance_score ?? 0,
    pocket: typeof point.pocket_rate === 'number' ? Math.round(point.pocket_rate * 100) : 0,
    mistake: typeof point.mistake_rate === 'number' ? Math.round(point.mistake_rate * 100) : 0,
    cue: point.cue_control_score ?? 0,
  }));

  const hasData = Boolean(overview?.has_data);

  return (
    <div className="space-y-4">
      <PageHeader title="數據" />
      <DropdownSelector value={value} onChange={onChange} />

      <div className="flex gap-2 overflow-x-auto pb-1">
        {(Object.keys(rangeLabels) as AnalyticsRange[]).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setRange(item)}
            className={`shrink-0 rounded-xl border px-3 py-2 text-xs font-black ${
              range === item ? 'border-cue-primary bg-cue-primary text-white' : 'border-cue-line bg-white text-cue-ink'
            }`}
          >
            {rangeLabels[item]}
          </button>
        ))}
      </div>

      {loading ? <p className="text-sm font-bold text-cue-muted">讀取真實數據中...</p> : null}
      {error ? <p className="rounded-xl border border-cue-danger/30 bg-white p-3 text-sm font-bold text-cue-danger">{error}</p> : null}
      {!loading && !error && overview && !hasData ? (
        <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
          <h2 className="text-sm font-black text-cue-ink">資料累積中</h2>
          <p className="mt-2 text-xs font-bold leading-5 text-cue-muted">
            目前沒有符合範圍的真實出桿資料。完成練習或遊戲出桿後，這裡會顯示表現分數、進球率與 AI 建議。
          </p>
        </section>
      ) : null}

      {overview ? (
        <>
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-black text-cue-ink">今日總覽</h2>
              <span className="text-[11px] font-black text-cue-muted">
                {overview.confidence === 'complete' ? '資料完整' : overview.confidence === 'partial' ? '資料累積中' : '尚無資料'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="今日表現分數" value={formatNumber(overview.performance_score, ' 分')} progress={overview.performance_score ?? 0} />
              <StatCard label="進球率" value={formatRate(overview.pocket_rate)} progress={(overview.pocket_rate ?? 0) * 100} tone="success" />
              <StatCard label="最常失誤" value={overview.most_common_mistake?.label || '資料累積中'} progress={overview.mistake_rate ? overview.mistake_rate * 100 : 0} tone="warning" />
              <StatCard label="AI 建議" value={overview.recommended_practice || '資料累積中'} />
            </div>
            <article className="mt-3 rounded-2xl border border-cue-line bg-white p-4 shadow-card">
              <p className="text-xs font-black text-cue-muted">建議摘要</p>
              <p className="mt-2 text-sm font-bold leading-6 text-cue-ink">{overview.ai_advice}</p>
            </article>
          </section>

          <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
            <h2 className="text-sm font-black text-cue-ink">母球控制</h2>
            <div className="mt-4 space-y-3">
              <MetricRow label="走位成功率" value={formatRate(overview.cue_control_rate)} progress={(overview.cue_control_rate ?? 0) * 100} />
              <MetricRow label="停點偏差" value={formatNumber(overview.average_cue_landing_error_px, ' px')} progress={overview.average_cue_landing_error_px ? Math.max(0, 100 - overview.average_cue_landing_error_px) : 0} />
              <MetricRow label="洗袋次數" value={`${overview.scratch_count} 次`} progress={Math.min(100, overview.scratch_count * 20)} tone="danger" />
              <MetricRow label="下一球好打比例" value={formatRate(overview.next_ball_good_rate)} progress={(overview.next_ball_good_rate ?? 0) * 100} />
            </div>
          </section>

          <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
            <h2 className="text-sm font-black text-cue-ink">練習紀錄</h2>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <StatCard label="今日出手數" value={`${overview.today_shots} 桿`} />
              <StatCard label="最佳連進" value={`${overview.best_streak} 球`} />
              <StatCard label="訓練完成率" value={formatRate(overview.training_completion_rate)} progress={(overview.training_completion_rate ?? 0) * 100} />
              <StatCard label="推薦練習" value={overview.recommended_practice || '資料累積中'} />
            </div>
          </section>
        </>
      ) : null}

      <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-black text-cue-ink">趨勢</h2>
          <div className="flex gap-1">
            {(Object.keys(bucketLabels) as TrendBucket[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setBucket(item)}
                className={`rounded-lg px-2 py-1 text-[11px] font-black ${
                  bucket === item ? 'bg-cue-primary text-white' : 'bg-slate-100 text-cue-muted'
                }`}
              >
                {bucketLabels[item]}
              </button>
            ))}
          </div>
        </div>
        {trendPoints.length > 0 ? (
          <>
            <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-bold text-cue-muted">
              <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-primary" />表現分數</span>
              <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-success" />進球率</span>
              <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-danger" />失誤率</span>
            </div>
            <div className="h-48">
              <ResponsiveContainer>
                <LineChart data={trendPoints} margin={{ left: -18, right: 6, top: 8, bottom: 0 }}>
                  <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#4F46E5" strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="pocket" stroke="#22C55E" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="mistake" stroke="#EF4444" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : (
          <p className="py-8 text-center text-sm font-bold text-cue-muted">尚無趨勢資料</p>
        )}
      </section>
    </div>
  );
}

function MetricRow({
  label,
  value,
  progress,
  tone = 'primary',
}: {
  label: string;
  value: string;
  progress: number;
  tone?: 'primary' | 'success' | 'danger' | 'warning';
}) {
  return (
    <div className="grid grid-cols-[88px_1fr_88px] items-center gap-3 text-xs font-bold">
      <span className="text-cue-ink">{label}</span>
      <ProgressBar value={progress} tone={tone} />
      <span className="text-right text-cue-muted">{value}</span>
    </div>
  );
}
