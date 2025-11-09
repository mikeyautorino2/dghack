import { GameCard } from './GameCard';
import type { ActiveMarket } from '@/types';

interface MarketGridProps {
  games: ActiveMarket[];
  isLoading?: boolean;
}

export function MarketGrid({ games, isLoading }: MarketGridProps) {
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (games.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-2">📊</div>
        <h3 className="text-lg font-medium mb-1">No active markets</h3>
        <p className="text-sm text-text-tertiary">
          Check back soon for upcoming games
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Upcoming Markets
        </h2>
        <p className="text-sm text-text-tertiary mt-1">
          {games.length} game{games.length !== 1 ? 's' : ''} with active Polymarket markets
        </p>
      </div>

      {/* Grid of game cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {games.map((game) => (
          <GameCard key={game.game_id} game={game} />
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 bg-bg-secondary rounded w-1/3 animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="bg-bg-secondary border border-border-subtle rounded-xl p-6 h-48 animate-pulse">
            <div className="h-4 bg-bg-tertiary rounded w-1/4 mb-4" />
            <div className="h-6 bg-bg-tertiary rounded w-3/4 mb-2" />
            <div className="h-6 bg-bg-tertiary rounded w-3/4 mb-4" />
            <div className="h-2 bg-bg-tertiary rounded w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
