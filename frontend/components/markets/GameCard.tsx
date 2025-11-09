import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import type { ActiveMarket } from '@/types';

interface GameCardProps {
  game: ActiveMarket;
}

export function GameCard({ game }: GameCardProps) {
  const awayPct = Math.round((game.polymarket_away_price || 0.5) * 100);
  const homePct = Math.round((game.polymarket_home_price || 0.5) * 100);

  return (
    <Link
      href={`/game/${game.sport.toLowerCase()}/${game.game_id}`}
      className="block group"
    >
      <div className="
        bg-bg-secondary border border-border-subtle rounded-xl p-6
        hover:border-border-default hover:bg-bg-hover
        transition-all duration-200
      ">
        {/* Header: Sport badge + Time */}
        <div className="flex items-center justify-between mb-4">
          <span className="
            text-xs font-medium uppercase tracking-wide
            text-text-tertiary bg-bg-tertiary px-2 py-1 rounded
          ">
            {game.sport}
          </span>
          <span className="text-xs text-text-tertiary">
            {formatDistanceToNow(game.game_start_ts * 1000, { addSuffix: true })}
          </span>
        </div>

        {/* Matchup */}
        <div className="space-y-3 mb-4">
          {/* Away team */}
          <div className="flex items-center justify-between">
            <span className="font-medium">{game.away_team}</span>
            <span className="text-lg font-semibold tabular-nums text-chart-away">
              {awayPct}%
            </span>
          </div>

          {/* Home team */}
          <div className="flex items-center justify-between">
            <span className="font-medium">{game.home_team}</span>
            <span className="text-lg font-semibold tabular-nums text-chart-home">
              {homePct}%
            </span>
          </div>
        </div>

        {/* Visual price indicator */}
        <div className="relative h-2 bg-bg-tertiary rounded-full overflow-hidden">
          <div
            className="absolute left-0 h-full bg-gradient-to-r from-chart-away to-accent-away transition-all duration-500"
            style={{ width: `${awayPct}%` }}
          />
          <div
            className="absolute right-0 h-full bg-gradient-to-l from-chart-home to-accent-home transition-all duration-500"
            style={{ width: `${homePct}%` }}
          />
        </div>

        {/* Hover indicator */}
        <div className="
          mt-4 text-xs text-text-tertiary
          group-hover:text-text-secondary transition-colors
          flex items-center gap-1
        ">
          View analysis
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </Link>
  );
}
