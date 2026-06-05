export default function ProgressBar({
  value,
  tone = 'primary',
}: {
  value: number;
  tone?: 'primary' | 'success' | 'danger' | 'warning';
}) {
  const color = {
    primary: 'bg-cue-primary',
    success: 'bg-cue-success',
    danger: 'bg-cue-danger',
    warning: 'bg-cue-warning',
  }[tone];

  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
