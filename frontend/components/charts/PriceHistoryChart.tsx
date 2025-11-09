'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { format } from 'date-fns';
import type { PricePoint, MarketMetadata } from '@/types';

interface PriceHistoryChartProps {
  priceHistory: PricePoint[];
  metadata: MarketMetadata | null;
  awayTeam: string;
  homeTeam: string;
  targetAwayTeam: string;
  targetHomeTeam: string;
  awayCorrespondsTo: 'home' | 'away';
  homeCorrespondsTo: 'home' | 'away';
}

export function PriceHistoryChart({
  priceHistory,
  metadata,
  awayTeam,
  homeTeam,
  targetAwayTeam,
  targetHomeTeam,
  awayCorrespondsTo,
  homeCorrespondsTo,
}: PriceHistoryChartProps) {
  // Transform data for Recharts and filter to relevant time period
  const chartData = useMemo(() => {
    // Filter to show only from game start onwards (preferred)
    let filteredHistory = priceHistory;

    if (metadata?.game_start_ts) {
      const gameStartMs = metadata.game_start_ts * 1000;
      const gameIntervalData = priceHistory.filter(
        point => point.timestamp * 1000 >= gameStartMs
      );

      // Use game interval if we have data, otherwise fall back to full history
      if (gameIntervalData.length > 0) {
        filteredHistory = gameIntervalData;
      } else if (metadata?.market_open_ts) {
        // Fallback: show from market open if no game interval data
        const marketOpenMs = metadata.market_open_ts * 1000;
        filteredHistory = priceHistory.filter(
          point => point.timestamp * 1000 >= marketOpenMs
        );
      }
    }

    // Transform to chart format
    // Swap prices if mapping is flipped so chart colors match legend
    const isFlipped = awayCorrespondsTo !== 'away' || homeCorrespondsTo !== 'home';

    return filteredHistory.map((point) => ({
      timestamp: point.timestamp * 1000, // Convert to milliseconds
      // If flipped, swap the prices so chart colors match team correspondence
      awayPrice: isFlipped ? (point.home_price * 100) : (point.away_price * 100),
      homePrice: isFlipped ? (point.away_price * 100) : (point.home_price * 100),
    }));
  }, [priceHistory, metadata, awayCorrespondsTo, homeCorrespondsTo]);

  // Check if we have data
  if (!chartData.length) {
    return (
      <div className="h-64 bg-bg-tertiary rounded-lg flex items-center justify-center text-text-tertiary">
        No price history available
      </div>
    );
  }

  // Custom tooltip - show which target team each line represents
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;

      // Calculate hours since game start
      let timeLabel = format(new Date(data.timestamp), 'MMM d, h:mm a');
      if (metadata?.game_start_ts) {
        const gameStartMs = metadata.game_start_ts * 1000;
        const hoursSinceStart = (data.timestamp - gameStartMs) / (1000 * 60 * 60);
        const minutes = Math.round((hoursSinceStart % 1) * 60);
        const hours = Math.floor(hoursSinceStart);

        if (hoursSinceStart >= 0) {
          timeLabel = `+${hours}h ${minutes}m`;
        } else {
          timeLabel = `${hours}h ${minutes}m`;
        }
      }

      return (
        <div className="bg-bg-secondary border border-border-default rounded-lg p-3 shadow-lg">
          <p className="text-xs text-text-tertiary mb-2">
            {timeLabel}
          </p>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-chart-away" />
              <span className="text-sm font-medium">
                {awayTeam} (≈ {awayCorrespondsTo === 'away' ? targetAwayTeam : targetHomeTeam}):
              </span>
              <span className="text-sm font-semibold tabular-nums">
                {data.awayPrice.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-chart-home" />
              <span className="text-sm font-medium">
                {homeTeam} (≈ {homeCorrespondsTo === 'home' ? targetHomeTeam : targetAwayTeam}):
              </span>
              <span className="text-sm font-semibold tabular-nums">
                {data.homePrice.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  // Format timestamp for X-axis - show hours since game start
  const formatXAxis = (timestamp: number) => {
    if (!metadata?.game_start_ts || chartData.length === 0) {
      return format(new Date(timestamp), 'h:mm a');
    }

    const gameStartMs = metadata.game_start_ts * 1000;
    const hoursSinceStart = (timestamp - gameStartMs) / (1000 * 60 * 60);

    // Show as hours (e.g., "0h", "1h", "2h", etc.)
    return `${Math.round(hoursSinceStart)}h`;
  };

  // Format Y-axis as percentage
  const formatYAxis = (value: number) => {
    return `${value}%`;
  };

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatXAxis}
            stroke="#666"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={formatYAxis}
            stroke="#666"
            style={{ fontSize: '12px' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
            formatter={(value: string) => {
              if (value === 'awayPrice') {
                const targetTeam = awayCorrespondsTo === 'away' ? targetAwayTeam : targetHomeTeam;
                return `${awayTeam} (≈ ${targetTeam})`;
              } else {
                const targetTeam = homeCorrespondsTo === 'home' ? targetHomeTeam : targetAwayTeam;
                return `${homeTeam} (≈ ${targetTeam})`;
              }
            }}
          />

          {/* Reference line for market close if available */}
          {metadata?.market_close_ts && (
            <ReferenceLine
              x={metadata.market_close_ts * 1000}
              stroke="#666"
              strokeDasharray="3 3"
              label={{
                value: 'Market Close',
                position: 'top',
                style: { fontSize: '10px', fill: '#999' },
              }}
            />
          )}

          <Line
            type="monotone"
            dataKey="awayPrice"
            stroke="rgb(167, 139, 250)" /* var(--color-chart-away) */
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="homePrice"
            stroke="rgb(52, 211, 153)" /* var(--color-chart-home) */
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
