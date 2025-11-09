'use client';

import { use, useEffect, useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import type { GameAnalysisResponse } from '@/types';

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
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        {similar.away_team} @ {similar.home_team}
                      </span>
                      {similar.mapping === 'flipped' && (
                        <span className="text-xs px-2 py-0.5 rounded bg-bg-tertiary text-text-tertiary border border-border-default">
                          Teams flipped
                        </span>
                      )}
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

                {/* Price history chart placeholder */}
                <div className="h-64 bg-bg-tertiary rounded-lg flex items-center justify-center text-text-tertiary">
                  Chart: {similar.price_history.length} price points
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
