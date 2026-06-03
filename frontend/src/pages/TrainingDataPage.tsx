import type { DataSection } from '../MobilePrototypeApp';
import DonutChart from '../components/DonutChart';
import DropdownSelector from '../components/DropdownSelector';
import PageHeader from '../components/PageHeader';
import ProgressBar from '../components/ProgressBar';

const shotBreakdown = [
  { label: '直球', rate: 82, count: '68 / 83' },
  { label: '薄球', rate: 76, count: '41 / 54' },
  { label: '厚球', rate: 71, count: '23 / 31' },
];

export default function TrainingDataPage({
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

      <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
        <h2 className="text-sm font-black text-cue-ink">進球成功率</h2>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-4xl font-black text-cue-ink">78%</p>
            <p className="mt-1 text-xs font-bold text-cue-muted">共 132 / 168</p>
          </div>
          <DonutChart value={78} />
        </div>
        <div className="mt-4 space-y-3">
          {shotBreakdown.map((item) => (
            <div key={item.label} className="grid grid-cols-[44px_1fr_62px] items-center gap-3 text-xs font-bold">
              <span className="text-cue-ink">{item.label}</span>
              <ProgressBar value={item.rate} />
              <span className="text-right text-cue-muted">{item.rate}% ({item.count})</span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-cue-line bg-white p-5 shadow-card">
        <h2 className="text-sm font-black text-cue-ink">開球成功率</h2>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-4xl font-black text-cue-ink">65%</p>
            <p className="mt-1 text-xs font-bold text-cue-muted">共 26 / 40</p>
          </div>
          <DonutChart value={65} />
        </div>
      </section>
    </div>
  );
}
