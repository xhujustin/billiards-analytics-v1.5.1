import { Grid3X3, Keyboard } from 'lucide-react';
import PageHeader from '../components/PageHeader';

function FakeQrCode() {
  const cells = Array.from({ length: 49 }, (_, index) => index);
  return (
    <div className="grid h-36 w-36 grid-cols-7 gap-1 bg-white p-2">
      {cells.map((cell) => (
        <span
          key={cell}
          className={`rounded-[2px] ${
            [0, 1, 2, 7, 14, 21, 22, 23, 5, 6, 12, 13, 19, 20, 35, 36, 42, 43, 44, 29, 31, 33, 38, 40, 46].includes(cell)
              ? 'bg-cue-ink'
              : 'bg-transparent'
          }`}
        />
      ))}
    </div>
  );
}

export default function ScanPage() {
  return (
    <div className="space-y-5">
      <PageHeader title="掃碼" />
      <section className="rounded-3xl border border-cue-line bg-white px-5 py-8 text-center shadow-soft">
        <h2 className="text-base font-black text-cue-ink">掃描對戰 QR Code</h2>
        <div className="relative mx-auto mt-10 grid h-56 w-56 place-items-center">
          <span className="absolute left-1 top-1 h-9 w-9 rounded-tl-xl border-l-4 border-t-4 border-cue-primary" />
          <span className="absolute right-1 top-1 h-9 w-9 rounded-tr-xl border-r-4 border-t-4 border-cue-primary" />
          <span className="absolute bottom-1 left-1 h-9 w-9 rounded-bl-xl border-b-4 border-l-4 border-cue-primary" />
          <span className="absolute bottom-1 right-1 h-9 w-9 rounded-br-xl border-b-4 border-r-4 border-cue-primary" />
          <FakeQrCode />
        </div>
        <div className="my-8 flex items-center gap-4 text-xs font-bold text-cue-muted">
          <span className="h-px flex-1 bg-cue-line" />
          <span>或</span>
          <span className="h-px flex-1 bg-cue-line" />
        </div>
        <button type="button" className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-cue-primary text-sm font-black text-white shadow-card">
          <Keyboard size={17} />
          輸入對戰碼
        </button>
        <button type="button" className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-cue-line bg-white text-sm font-black text-cue-ink">
          <Grid3X3 size={17} />
          我的 QR Code
        </button>
      </section>
    </div>
  );
}
