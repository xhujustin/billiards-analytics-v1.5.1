import { ChevronRight } from 'lucide-react';

export interface MatchRowData {
  opponent: string;
  result: '勝利' | '失敗';
  score: string;
  meta: string;
  points: string;
  time: string;
}

export default function MatchRow({ match, compact = false }: { match: MatchRowData; compact?: boolean }) {
  const isWin = match.result === '勝利';
  return (
    <div className="flex items-center justify-between border-b border-cue-line py-3 last:border-b-0">
      <div>
        <p className="text-sm font-extrabold text-cue-ink">vs {match.opponent}</p>
        <p className="mt-1 text-[11px] font-medium text-cue-muted">
          {match.meta} {!compact ? ` · ${match.points}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className={`text-xs font-black ${isWin ? 'text-cue-success' : 'text-cue-danger'}`}>{match.result}</p>
          <p className="mt-0.5 text-sm font-black text-cue-ink">{match.score}</p>
          <p className="text-[11px] font-medium text-cue-muted">{match.time}</p>
        </div>
        {!compact ? <ChevronRight size={16} className="text-cue-muted" /> : null}
      </div>
    </div>
  );
}
