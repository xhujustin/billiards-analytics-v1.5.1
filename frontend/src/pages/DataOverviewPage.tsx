import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DataSection } from '../MobilePrototypeApp';
import DropdownSelector from '../components/DropdownSelector';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';

const cards = [
  ['進攻成功率', '78%', 78],
  ['開球成功率', '65%', 65],
  ['防守成功率', '58%', 58],
  ['平均得分', '4.2', 62],
  ['失誤率', '22%', 22],
  ['長台成功率', '48%', 48],
] as const;

const trend = [
  { day: '4/28', score: 1120, pocket: 48, error: 22 },
  { day: '5/03', score: 1110, pocket: 55, error: 28 },
  { day: '5/06', score: 1180, pocket: 44, error: 24 },
  { day: '5/12', score: 1210, pocket: 40, error: 16 },
  { day: '5/16', score: 1260, pocket: 58, error: 21 },
  { day: '5/19', score: 1250, pocket: 52, error: 9 },
  { day: '5/23', score: 1330, pocket: 58, error: 10 },
  { day: '5/26', score: 1370, pocket: 61, error: 10 },
];

export default function DataOverviewPage({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (section: DataSection) => void;
}) {
  return (
    <div className="space-y-4">
      <PageHeader title="數據" />
      <DropdownSelector value={value} onChange={onChange} />

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-black text-cue-ink">關鍵數據</h2>
          <button type="button" className="text-xs font-black text-cue-primary">編輯卡片</button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {cards.map(([label, cardValue, progress]) => (
            <StatCard key={label} label={label} value={cardValue} progress={progress} />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-black text-cue-ink">表現趨勢</h2>
          <button type="button" className="rounded-xl border border-cue-line px-3 py-2 text-xs font-bold text-cue-ink">過去 30 天</button>
        </div>
        <div className="mb-3 flex gap-4 text-[11px] font-bold text-cue-muted">
          <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-primary" />積分</span>
          <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-success" />進球成功率</span>
          <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cue-danger" />失誤率</span>
        </div>
        <div className="h-48">
          <ResponsiveContainer>
            <LineChart data={trend} margin={{ left: -18, right: 6, top: 8, bottom: 0 }}>
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6B7280' }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="left" hide domain={[1000, 1400]} />
              <YAxis yAxisId="right" hide domain={[0, 100]} />
              <Tooltip />
              <Line yAxisId="left" type="monotone" dataKey="score" stroke="#4F46E5" strokeWidth={3} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="pocket" stroke="#22C55E" strokeWidth={2.5} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="error" stroke="#EF4444" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
