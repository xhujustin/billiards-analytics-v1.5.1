import { BarChart3, Home, QrCode, User, Users } from 'lucide-react';

export type MainTab = '首頁' | '數據' | '掃碼' | '好友' | '我的';

const navItems: Array<{ key: MainTab; icon: typeof Home }> = [
  { key: '首頁', icon: Home },
  { key: '數據', icon: BarChart3 },
  { key: '掃碼', icon: QrCode },
  { key: '好友', icon: Users },
  { key: '我的', icon: User },
];

export default function BottomNav({ activeTab, onChange }: { activeTab: MainTab; onChange: (tab: MainTab) => void }) {
  return (
    <nav className="absolute inset-x-0 bottom-0 border-t border-cue-line bg-white/95 px-5 pb-4 pt-2 backdrop-blur">
      <div className="grid grid-cols-5 gap-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeTab === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onChange(item.key)}
              className={`flex h-12 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-bold transition ${
                active ? 'text-cue-primary' : 'text-cue-muted'
              }`}
            >
              <Icon size={19} strokeWidth={active ? 2.8 : 2.2} />
              <span>{item.key}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
