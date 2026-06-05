import { Bell, ShieldCheck } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import MatchRow, { type MatchRowData } from '../components/MatchRow';
import ProgressBar from '../components/ProgressBar';
import StatCard from '../components/StatCard';

const recentMatches: MatchRowData[] = [
  { opponent: 'Kevin', result: '勝利', score: '9:6', meta: '9 球 · 7 局', points: '+18 分', time: '今天 15:30' },
  { opponent: 'Jack', result: '失敗', score: '6:9', meta: '9 球 · 7 局', points: '-16 分', time: '昨天 18:20' },
  { opponent: 'Tom', result: '勝利', score: '9:4', meta: '9 球 · 7 局', points: '+16 分', time: '05/10 20:15' },
];

const monthlyTrend = [
  { day: '5/01', score: 870 },
  { day: '5/05', score: 1030 },
  { day: '5/08', score: 1070 },
  { day: '5/12', score: 1120 },
  { day: '5/15', score: 1100 },
  { day: '5/19', score: 1210 },
  { day: '5/22', score: 1240 },
  { day: '5/26', score: 1310 },
  { day: '5/29', score: 1340 },
];

export default function HomePage() {
  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-12 w-12 rounded-full bg-gradient-to-br from-slate-200 to-slate-300" />
          <div>
            <h1 className="text-lg font-black text-cue-ink">Lucian</h1>
            <p className="text-xs font-bold text-cue-muted">進階玩家 II</p>
          </div>
        </div>
        <button type="button" className="grid h-10 w-10 place-items-center rounded-full bg-white shadow-card">
          <Bell size={19} className="text-cue-ink" />
        </button>
      </header>

      <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 p-5 text-white shadow-soft">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-bold text-slate-300">積分</p>
            <p className="mt-1 text-4xl font-black tracking-tight">1280</p>
            <p className="mt-2 text-sm font-bold text-slate-300">排名 5,245 <span className="ml-2 text-cue-success">↑ 18</span></p>
          </div>
          <div className="grid h-16 w-16 place-items-center rounded-full bg-white/10">
            <ShieldCheck size={34} className="text-cue-success" />
          </div>
        </div>
        <div className="mt-6">
          <ProgressBar value={78} />
          <div className="mt-2 flex justify-between text-xs font-bold text-slate-300">
            <span>距離下一等級還差 220 分</span>
            <span>1500</span>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-3 gap-3">
        <StatCard label="勝率" value="62%" />
        <StatCard label="總場次" value="48" />
        <StatCard label="連勝" value="5" />
      </div>

      <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-black text-cue-ink">最近對戰記錄</h2>
          <button type="button" className="text-xs font-black text-cue-primary">查看全部</button>
        </div>
        {recentMatches.map((match) => (
          <MatchRow key={match.opponent} match={match} compact />
        ))}
      </section>

      <section className="rounded-2xl border border-cue-line bg-white p-4 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-black text-cue-ink">本月表現</h2>
          <div className="text-right">
            <p className="text-[11px] font-bold text-cue-muted">積分變化</p>
            <p className="text-sm font-black text-cue-success">+128</p>
          </div>
        </div>
        <div className="h-32">
          <ResponsiveContainer>
            <LineChart data={monthlyTrend} margin={{ left: -20, right: 6, top: 8, bottom: 0 }}>
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6B7280' }} axisLine={false} tickLine={false} />
              <YAxis hide domain={['dataMin - 60', 'dataMax + 40']} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#4F46E5" strokeWidth={3} dot={{ r: 3, fill: '#4F46E5' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
