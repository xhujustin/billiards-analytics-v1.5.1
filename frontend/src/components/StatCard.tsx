import ProgressBar from './ProgressBar';

export default function StatCard({
  label,
  value,
  progress,
  tone = 'primary',
}: {
  label: string;
  value: string;
  progress?: number;
  tone?: 'primary' | 'success' | 'danger' | 'warning';
}) {
  return (
    <article className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
      <p className="text-xs font-bold text-cue-muted">{label}</p>
      <p className="mt-3 text-2xl font-black tracking-tight text-cue-ink">{value}</p>
      {typeof progress === 'number' ? (
        <div className="mt-3">
          <ProgressBar value={progress} tone={tone} />
        </div>
      ) : null}
    </article>
  );
}
