'use client';

import { use, useEffect, useState, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { PriceHistoryChart } from '@/components/charts/PriceHistoryChart';
import type { GameAnalysisResponse } from '@/types';

interface LiveMarket {
  exists: boolean;
  market_id: string | null;
  polymarket_slug: string | null;
  away_team: string;
  home_team: string;
  away_price: number | null;
  home_price: number | null;
  timestamp: number | null;
}

interface PricePoint {
  timestamp: number;
  away_price: number;
  home_price: number;
}

export default function GameDetailPage({
  params,
}: {
  params: Promise<{ sport: string; gameId: string }>;
}) {
  const { sport, gameId } = use(params);
  const [data, setData] = useState<GameAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [k, setK] = useState(5);

  // Live market state
  const [liveMarket, setLiveMarket] = useState<LiveMarket | null>(null);
  const [livePriceHistory, setLivePriceHistory] = useState<PricePoint[]>([]);
  const [isLoadingLiveMarket, setIsLoadingLiveMarket] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Fetch live market data - wrapped in useCallback to avoid recreating on every render
  const fetchLiveMarket = useCallback(async () => {
    setIsLoadingLiveMarket(true);
    try {
      const response = await fetch(
        `/api/games/${sport}/${gameId}/live-market`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch live market');
      }

      const result: LiveMarket = await response.json();
      setLiveMarket(result);

      // If market exists and has price data, add to history
      if (result.exists && result.away_price !== null && result.home_price !== null && result.timestamp) {
        const newPricePoint: PricePoint = {
          timestamp: result.timestamp,
          away_price: result.away_price,
          home_price: result.home_price,
        };

        setLivePriceHistory((prev) => {
          // Avoid duplicates - check if this timestamp already exists
          const exists = prev.some(p => p.timestamp === newPricePoint.timestamp);
          if (exists) {
            return prev;
          }
          return [...prev, newPricePoint].sort((a, b) => a.timestamp - b.timestamp);
        });

        setLastUpdate(new Date());
      }
    } catch (err) {
      console.error('Failed to fetch live market:', err);
    } finally {
      setIsLoadingLiveMarket(false);
    }
  }, [sport, gameId]);

  // Fetch historical analysis data
  useEffect(() => {
    async function fetchAnalysis() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/games/${sport}/${gameId}/analysis?k=${k}`
        );

        if (!response.ok) {
          throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        console.log('API Response:', result);
        setData(result);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch analysis';
        console.error('Failed to fetch analysis:', err);
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    }

    fetchAnalysis();
  }, [sport, gameId, k]);

  // Fetch live market immediately on mount, then poll every 7 minutes
  useEffect(() => {
    // Immediate fetch when page loads - user sees data right away
    fetchLiveMarket();

    // Set up polling interval (7 minutes = 420,000 milliseconds)
    // This will fire 7 minutes AFTER the initial fetch
    const interval = setInterval(fetchLiveMarket, 7 * 60 * 1000);

    // Cleanup on unmount
    return () => clearInterval(interval);
  }, [fetchLiveMarket]); // Include fetchLiveMarket in dependencies

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-2 border-accent-primary border-t-transparent rounded-full" />
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="text-center py-20">
          <div className="text-4xl mb-2">⚠️</div>
          <h3 className="text-lg font-medium mb-1">Error loading game analysis</h3>
          <p className="text-sm text-text-tertiary">{error}</p>
        </div>
      </AppShell>
    );
  }

  if (!data || !data.target_game) {
    return (
      <AppShell>
        <div className="text-center py-20">
          <p className="text-text-tertiary">Game not found</p>
        </div>
      </AppShell>
    );
  }

  const { target_game, similar_games } = data;

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Target Game Header */}
        <div className="bg-bg-secondary border border-border-subtle rounded-2xl p-8">
          <div className="mb-6">
            <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary bg-bg-tertiary px-3 py-1.5 rounded-lg">
              {target_game.sport}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="text-xs uppercase tracking-wide text-text-tertiary mb-2">
                Away
              </div>
              <div className="text-3xl font-semibold tracking-tight">
                {target_game.away_team}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-text-tertiary mb-2">
                Home
              </div>
              <div className="text-3xl font-semibold tracking-tight">
                {target_game.home_team}
              </div>
            </div>
          </div>
        </div>

        {/* Live Market Section */}
        {liveMarket && liveMarket.exists && (
          <div className="bg-bg-secondary border border-border-subtle rounded-2xl p-8">
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold tracking-tight">
                  Current Market (Live)
                </h2>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-xs text-text-tertiary">
                    {isLoadingLiveMarket ? 'Updating...' : 'Live'}
                  </span>
                </div>
              </div>
              {lastUpdate && (
                <span className="text-xs text-text-tertiary">
                  Last updated: {Math.floor((Date.now() - lastUpdate.getTime()) / 1000 / 60)} min ago
                </span>
              )}
            </div>

            {/* Current Prices */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="bg-bg-tertiary rounded-lg p-4">
                <div className="text-xs uppercase tracking-wide text-text-tertiary mb-2">
                  {liveMarket.away_team}
                </div>
                <div className="text-3xl font-bold tabular-nums">
                  {liveMarket.away_price !== null ? `${(liveMarket.away_price * 100).toFixed(1)}%` : '--'}
                </div>
              </div>
              <div className="bg-bg-tertiary rounded-lg p-4">
                <div className="text-xs uppercase tracking-wide text-text-tertiary mb-2">
                  {liveMarket.home_team}
                </div>
                <div className="text-3xl font-bold tabular-nums">
                  {liveMarket.home_price !== null ? `${(liveMarket.home_price * 100).toFixed(1)}%` : '--'}
                </div>
              </div>
            </div>

            {/* Live Price History Chart */}
            {livePriceHistory.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-text-secondary mb-4">
                  Price History (This Session)
                </h3>
                <PriceHistoryChart
                  priceHistory={livePriceHistory}
                  metadata={null}
                  awayTeam={liveMarket.away_team}
                  homeTeam={liveMarket.home_team}
                  targetAwayTeam={liveMarket.away_team}
                  targetHomeTeam={liveMarket.home_team}
                  awayCorrespondsTo="away"
                  homeCorrespondsTo="home"
                  isLiveData={true}
                />
              </div>
            )}

            {livePriceHistory.length === 0 && (
              <div className="text-center py-8 text-text-tertiary text-sm">
                Accumulating price data... Check back in 7 minutes for price history chart
              </div>
            )}
          </div>
        )}

        {liveMarket && !liveMarket.exists && (
          <div className="bg-bg-secondary border border-border-subtle rounded-2xl p-8">
            <div className="text-center py-8">
              <div className="text-4xl mb-2">📊</div>
              <h3 className="text-lg font-medium mb-1">No Active Polymarket Market</h3>
              <p className="text-sm text-text-tertiary">
                This game does not have an active betting market on Polymarket
              </p>
            </div>
          </div>
        )}

        {/* Similar Games Section */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">
                {k} Most Similar Historical Matchups
              </h2>
              <p className="text-sm text-text-tertiary mt-1">
                Based on cumulative team statistics using K-Nearest Neighbors
              </p>
            </div>

            <select
              className="bg-bg-secondary border border-border-default rounded-lg px-4 py-2 text-sm"
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
            </select>
          </div>

          {/* Similar game cards */}
          <div className="space-y-6">
            {similar_games.map((similar, idx) => (
              <div
                key={similar.game_id}
                className="bg-bg-secondary border border-border-subtle rounded-xl p-6"
              >
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-bg-tertiary flex items-center justify-center text-sm font-semibold text-text-tertiary">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">
                      <span className="text-chart-away">
                        {similar.away_team}
                      </span>
                      {' @ '}
                      <span className="text-chart-home">
                        {similar.home_team}
                      </span>
                    </div>
                    <div className="text-sm text-text-tertiary">{similar.date}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs uppercase tracking-wide text-text-tertiary mb-1">
                      Similarity
                    </div>
                    <div className="text-xl font-semibold tabular-nums">
                      {Math.round(similar.similarity)}%
                    </div>
                  </div>
                </div>

                {/* Price history chart */}
                <PriceHistoryChart
                  priceHistory={similar.price_history}
                  metadata={similar.market_metadata}
                  awayTeam={similar.away_team}
                  homeTeam={similar.home_team}
                  targetAwayTeam={target_game.away_team}
                  targetHomeTeam={target_game.home_team}
                  awayCorrespondsTo={similar.current_away_corresponds_to}
                  homeCorrespondsTo={similar.current_home_corresponds_to}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
