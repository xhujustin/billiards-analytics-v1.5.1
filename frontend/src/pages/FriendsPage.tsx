import { Search, UserPlus } from 'lucide-react';
import FriendRow, { type FriendRowData } from '../components/FriendRow';
import PageHeader from '../components/PageHeader';

const friends: FriendRowData[] = [
  { rank: 1, name: 'Kevin', level: '進階玩家 II', score: 1280, status: '在線' },
  { rank: 2, name: 'Jack', level: '進階玩家 I', score: 1262, status: '在線' },
  { rank: 3, name: 'Tom', level: '進階玩家 II', score: 1250, status: '離開' },
  { rank: 4, name: 'Eric', level: '新手玩家 III', score: 1108, status: '離線' },
  { rank: 5, name: 'Jerry', level: '進階玩家 I', score: 1185, status: '在線' },
  { rank: 6, name: 'Peter', level: '新手玩家 II', score: 1050, status: '離線' },
];

export default function FriendsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="好友"
        action={
          <button type="button" className="grid h-9 w-9 place-items-center rounded-full bg-white shadow-card">
            <UserPlus size={18} className="text-cue-ink" />
          </button>
        }
      />
      <label className="flex h-11 items-center gap-2 rounded-2xl bg-white px-4 shadow-sm">
        <Search size={17} className="text-cue-muted" />
        <input className="min-w-0 flex-1 bg-transparent text-sm font-bold outline-none placeholder:text-cue-muted" placeholder="搜尋好友" />
      </label>
      <div className="grid grid-cols-2 border-b border-cue-line text-sm font-bold">
        <button type="button" className="border-b-2 border-cue-primary pb-3 text-cue-primary">好友列表</button>
        <button type="button" className="pb-3 text-cue-muted">好友申請</button>
      </div>
      <section className="rounded-2xl border border-cue-line bg-white px-4 shadow-card">
        {friends.map((friend) => (
          <FriendRow key={friend.name} friend={friend} />
        ))}
      </section>
    </div>
  );
}
