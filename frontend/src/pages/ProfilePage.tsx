import { Bell, ChevronRight, Info, Lock, LogOut, Settings, UserRound } from 'lucide-react';
import PageHeader from '../components/PageHeader';

const settings = [
  { label: '個人資料', icon: UserRound },
  { label: '帳號設定', icon: Settings },
  { label: '隱私設定', icon: Lock },
  { label: '通知設定', icon: Bell },
  { label: '關於 CueVex', icon: Info },
  { label: '登出', icon: LogOut },
];

export default function ProfilePage() {
  return (
    <div className="space-y-5">
      <PageHeader title="" />
      <section className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-card">
        <div className="h-14 w-14 rounded-full bg-gradient-to-br from-slate-200 to-slate-300" />
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-black text-cue-ink">Lucian</h1>
          <p className="mt-1 inline-flex rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-black text-emerald-700">進階玩家 II</p>
          <p className="mt-1 text-xs font-bold text-cue-muted">ID: CUEVEX_1024</p>
        </div>
        <ChevronRight size={18} className="text-cue-muted" />
      </section>

      <section className="rounded-2xl border border-cue-line bg-white px-4 shadow-card">
        {settings.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.label} type="button" className="flex w-full items-center gap-3 border-b border-cue-line py-4 text-left last:border-b-0">
              <Icon size={18} className={item.label === '登出' ? 'text-cue-danger' : 'text-cue-muted'} />
              <span className={`flex-1 text-sm font-black ${item.label === '登出' ? 'text-cue-danger' : 'text-cue-ink'}`}>{item.label}</span>
              <ChevronRight size={16} className="text-cue-muted" />
            </button>
          );
        })}
      </section>
    </div>
  );
}
