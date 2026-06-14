import { useEffect, useState } from 'react';
import type { DataSection } from '../MobilePrototypeApp';
import DonutChart from '../components/DonutChart';
import DropdownSelector from '../components/DropdownSelector';
import PageHeader from '../components/PageHeader';
import ProgressBar from '../components/ProgressBar';

type AnalyticsRange = 'today' | 'week' | 'month' | 'year';

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

const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';

const rangeLabels: Record<AnalyticsRange, string> = {
  today: '今日',
  week: '近 7 天',
  month: '近 30 天',
  year: '近一年',
};

const distanceLabels: Record<string, string> = {
  near: '近球',
  mid: '中距離',
  far: '遠球',
};

const difficultyLabels: Record<string, string> = {
  easy: '簡單球',
  medium: '中等球',
  hard: '困難球',
};

const thicknessLabels: Record<string, string> = {
  too_thick: '打厚',
  too_thin: '打薄',
  on_line: '準線',
  unknown: '未知',
};

const formatRate = (rate: number | null) => (typeof rate === 'number' ? `${Math.round(rate * 100)}%` : '資料累積中');

export default function TrainingDataPage({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (section: DataSection) => void;
}) {
  const [range, setRange] = useState<AnalyticsRange>('today');
  const [data, setData] = useState<OffensePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/api/analytics/offense?range=${range}`);
        if (!response.ok) throw new Error('offense api failed');
        const payload = await response.json();
        if (!cancelled) setData(payload);
      } catch {
        if (!cancelled) {
          setError('無法讀取進攻數據，請確認後端服務已啟動。');
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [range]);

  const totalShots = data?.distance_buckets.reduce((sum, item) => sum + item.shots, 0) || 0;
  const totalMade = data?.distance_buckets.reduce((sum, item) => sum + item.made, 0) || 0;
  const overallRate = totalShots > 0 ? totalMade / totalShots : null;

  return (
    <div className="space-y-4">
      <PageHeader title="數據" />
      <div className="flex items-center justify-between gap-3">
        <DropdownSelector value={value} onChange={onChange} />
      </div>

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

      {loading ? <p className="text-sm font-bold text-cue-muted">讀取真實進攻數據中...</p> : null}
      {error ? <p className="rounded-xl border border-cue-danger/30 bg-white p-3 text-sm font-bold text-cue-danger">{error}</p> : null}

      {data && !data.has_data ? (
        <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
          <h2 className="text-sm font-black text-cue-ink">資料累積中</h2>
          <p className="mt-2 text-xs font-bold leading-5 text-cue-muted">
            目前沒有符合範圍的真實出桿資料。完成幾次練習後，這裡會顯示近中遠距離、難度與厚薄分析。
          </p>
        </section>
      ) : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
            <h2 className="text-sm font-black text-cue-ink">進球成功率</h2>
            <div className="mt-4 flex items-center justify-between">
              <div>
                <p className="text-4xl font-black text-cue-ink">{formatRate(overallRate)}</p>
                <p className="mt-1 text-xs font-bold text-cue-muted">共 {totalMade} / {totalShots} 桿</p>
              </div>
              <DonutChart value={(overallRate ?? 0) * 100} />
            </div>
          </section>

          <AnalyticsSection
            title="近 / 中 / 遠進球率"
            buckets={data.distance_buckets}
            labelMap={distanceLabels}
          />

          <AnalyticsSection
            title="簡單 / 中等 / 困難球成功率"
            buckets={data.difficulty_buckets}
            labelMap={difficultyLabels}
          />

          <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
            <h2 className="text-sm font-black text-cue-ink">打厚 / 打薄</h2>
            <div className="mt-4 space-y-3">
              {data.thickness.map((item) => (
                <CountRow
                  key={item.type}
                  label={thicknessLabels[item.type] || item.type}
                  count={item.count}
                  total={Math.max(1, data.thickness.reduce((sum, entry) => sum + entry.count, 0))}
                />
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
            <h2 className="text-sm font-black text-cue-ink">失誤方向</h2>
            <div className="mt-4 space-y-3">
              {data.mistakes.length > 0 ? data.mistakes.map((item) => (
                <CountRow
                  key={item.type}
                  label={item.label || item.type}
                  count={item.count}
                  total={Math.max(1, data.mistakes.reduce((sum, entry) => sum + entry.count, 0))}
                  tone="warning"
                />
              )) : (
                <p className="text-sm font-bold text-cue-muted">目前沒有明顯失誤資料</p>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function AnalyticsSection({
  title,
  buckets,
  labelMap,
}: {
  title: string;
  buckets: RateBucket[];
  labelMap: Record<string, string>;
}) {
  return (
    <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
      <h2 className="text-sm font-black text-cue-ink">{title}</h2>
      <div className="mt-4 space-y-3">
        {buckets.map((item) => (
          <div key={item.bucket} className="grid grid-cols-[58px_1fr_76px] items-center gap-3 text-xs font-bold">
            <span className="text-cue-ink">{labelMap[item.bucket] || item.bucket}</span>
            <ProgressBar value={(item.rate ?? 0) * 100} />
            <span className="text-right text-cue-muted">{formatRate(item.rate)} ({item.made}/{item.shots})</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CountRow({
  label,
  count,
  total,
  tone = 'primary',
}: {
  label: string;
  count: number;
  total: number;
  tone?: 'primary' | 'success' | 'danger' | 'warning';
}) {
  const rate = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="grid grid-cols-[58px_1fr_50px] items-center gap-3 text-xs font-bold">
      <span className="text-cue-ink">{label}</span>
      <ProgressBar value={rate} tone={tone} />
      <span className="text-right text-cue-muted">{count} 次</span>
    </div>
  );
}
