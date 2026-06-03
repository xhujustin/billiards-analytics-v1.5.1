import type { ReactNode } from 'react';

export default function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <header className="mb-5 flex min-h-9 items-center justify-center">
      <h1 className="text-center text-lg font-black tracking-tight text-cue-ink">{title}</h1>
      <div className="absolute right-5">{action}</div>
    </header>
  );
}
