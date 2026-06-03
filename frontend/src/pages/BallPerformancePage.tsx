import type { DataSection } from '../MobilePrototypeApp';
import DropdownSelector from '../components/DropdownSelector';
import PageHeader from '../components/PageHeader';
import ProgressBar from '../components/ProgressBar';

const balls = [
  { ball: '1 號球', rate: 85, count: 26 },
  { ball: '2 號球', rate: 80, count: 24 },
  { ball: '3 號球', rate: 75, count: 20 },
  { ball: '4 號球', rate: 70, count: 18 },
  { ball: '5 號球', rate: 65, count: 17 },
  { ball: '6 號球', rate: 62, count: 16 },
  { ball: '7 號球', rate: 60, count: 15 },
  { ball: '8 號球', rate: 50, count: 14 },
];

const ballColors = ['bg-amber-400', 'bg-blue-500', 'bg-red-500', 'bg-purple-500', 'bg-orange-500', 'bg-green-500', 'bg-rose-700', 'bg-slate-900'];

export default function BallPerformancePage({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (section: DataSection) => void;
}) {
  return (
    <div className="space-y-4">
      <PageHeader title="數據" />
      <div className="flex items-center justify-between">
        <DropdownSelector value={value} onChange={onChange} />
        <button type="button" className="rounded-xl border border-cue-line bg-white px-3 py-2 text-xs font-bold text-cue-ink shadow-sm">過去 30 天</button>
      </div>
      <section className="rounded-2xl border border-cue-line bg-white px-4 shadow-card">
        {balls.map((item, index) => (
          <div key={item.ball} className="grid grid-cols-[34px_76px_1fr_52px] items-center gap-2 border-b border-cue-line py-3 last:border-b-0">
            <span className={`grid h-5 w-5 place-items-center rounded-full text-[10px] font-black text-white ${ballColors[index]}`}>{index + 1}</span>
            <p className="text-sm font-black text-cue-ink">{item.ball}</p>
            <div>
              <div className="mb-1 flex justify-between text-[11px] font-bold text-cue-muted">
                <span>進球率 {item.rate}%</span>
              </div>
              <ProgressBar value={item.rate} />
            </div>
            <p className="text-right text-xs font-black text-cue-ink">{item.count}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
