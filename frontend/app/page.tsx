'use client';

import { useEffect, useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { MarketGrid } from '@/components/markets/MarketGrid';
import type { ActiveMarket } from '@/types';

export default function HomePage() {
  const [games, setGames] = useState<ActiveMarket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchGames() {
      setIsLoading(true);
      setError(null);
      try {
        // Fetch upcoming games with active markets
        const response = await fetch('/api/markets');
        if (!response.ok) {
          throw new Error('Failed to fetch markets');
        }
        const data = await response.json();

        // Transform API response to match our type
        const transformedGames: ActiveMarket[] = data.map((market: any) => ({
          game_id: market.game_id,
          sport: market.sport,
          game_date: market.game_date,
          away_team: market.away_team,
          home_team: market.home_team,
          game_start_ts: market.game_start_ts,
          polymarket_away_price: market.polymarket_away_price,
          polymarket_home_price: market.polymarket_home_price,
        }));

        setGames(transformedGames);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
        console.error('Failed to fetch games:', err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchGames();

    // Poll for price updates every 5 minutes
    const interval = setInterval(fetchGames, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <AppShell>
      {error ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-2">⚠️</div>
          <h3 className="text-lg font-medium mb-1">Error loading markets</h3>
          <p className="text-sm text-text-tertiary">{error}</p>
        </div>
      ) : (
        <MarketGrid games={games} isLoading={isLoading} />
      )}
    </AppShell>
  );
}
