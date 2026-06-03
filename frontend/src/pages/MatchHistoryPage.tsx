import { useMemo, useState } from 'react';
import type { DataSection } from '../MobilePrototypeApp';
import DropdownSelector from '../components/DropdownSelector';
import MatchRow, { type MatchRowData } from '../components/MatchRow';
import PageHeader from '../components/PageHeader';

const matches: MatchRowData[] = [
  { opponent: 'Kevin', result: '勝利', score: '9:6', meta: '9 球 · 7 局', points: '+18分', time: '今天 15:30' },
  { opponent: 'Jack', result: '失敗', score: '6:9', meta: '9 球 · 7 局', points: '-16分', time: '昨天 18:20' },
  { opponent: 'Tom', result: '勝利', score: '9:4', meta: '9 球 · 7 局', points: '+16分', time: '05/10 20:15' },
  { opponent: 'Eric', result: '勝利', score: '9:7', meta: '9 球 · 7 局', points: '+14分', time: '05/09 21:10' },
  { opponent: 'Jerry', result: '失敗', score: '7:9', meta: '9 球 · 7 局', points: '-12分', time: '05/07 16:40' },
  { opponent: 'Peter', result: '勝利', score: '9:5', meta: '9 球 · 7 局', points: '+13分', time: '05/05 19:30' },
];

type ResultFilter = '全部' | '勝利' | '失敗';

export default function MatchHistoryPage({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (section: DataSection) => void;
}) {
  const [filter, setFilter] = useState<ResultFilter>('全部');
  const filteredMatches = useMemo(
    () => (filter === '全部' ? matches : matches.filter((match) => match.result === filter)),
    [filter],
  );

  return (
    <div className="space-y-4">
      <PageHeader title="數據" />
      <DropdownSelector value={value} onChange={onChange} />
      <div className="grid grid-cols-3 border-b border-cue-line text-sm font-bold text-cue-muted">
        {(['全部', '勝利', '失敗'] as ResultFilter[]).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setFilter(item)}
            className={`pb-3 ${filter === item ? 'border-b-2 border-cue-primary text-cue-primary' : ''}`}
          >
            {item}
          </button>
        ))}
      </div>
      <section className="rounded-2xl border border-cue-line bg-white px-4 shadow-card">
        {filteredMatches.map((match) => (
          <MatchRow key={`${match.opponent}-${match.time}`} match={match} />
        ))}
      </section>
    </div>
  );
}
