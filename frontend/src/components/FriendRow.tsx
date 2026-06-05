import { Medal } from 'lucide-react';

export interface FriendRowData {
  rank: number;
  name: string;
  level: string;
  score: number;
  status: '在線' | '離開' | '離線';
}

export default function FriendRow({ friend }: { friend: FriendRowData }) {
  const statusColor = friend.status === '在線' ? 'bg-cue-success' : friend.status === '離開' ? 'bg-cue-warning' : 'bg-slate-400';
  const medalColor = friend.rank === 1 ? 'text-amber-500' : friend.rank === 2 ? 'text-blue-500' : friend.rank === 3 ? 'text-orange-500' : 'text-slate-400';

  return (
    <div className="flex items-center gap-3 border-b border-cue-line py-3 last:border-b-0">
      <div className="relative grid h-10 w-10 place-items-center rounded-full bg-slate-200 text-sm font-black text-cue-muted">
        {friend.name.slice(0, 1)}
        <span className="absolute -left-1 -top-1 grid h-5 w-5 place-items-center rounded-full bg-white shadow-sm">
          <Medal size={14} className={medalColor} />
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-black text-cue-ink">{friend.name}</p>
        <p className="text-[11px] font-medium text-cue-muted">{friend.level}</p>
      </div>
      <p className="text-xs font-black text-cue-ink">{friend.score} 分</p>
      <span className={`h-2 w-2 rounded-full ${statusColor}`} />
    </div>
  );
}
