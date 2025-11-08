#!/usr/bin/env python3
"""
Market Price Tracking Service

Continuously tracks current prices for all active Polymarket markets.
Stores price snapshots every 5 minutes for historical analysis and candlestick charts.

Run frequency: Every 5 minutes via cron
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo

# Import service APIs
from backend.services import polymarket_api
from backend.app import db


async def track_market_price(session: aiohttp.ClientSession, market: dict) -> bool:
    """
    Fetch and store current price for a single market.

    Args:
        session: aiohttp session
        market: Market dict from database

    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract team names from polymarket_slug
        # Format: "nfl-giants-broncos-2024-11-08" or "nba-lal-bos-2024-12-25"
        slug_parts = market['polymarket_slug'].split('-')
        sport = slug_parts[0]

        # Find the date (YYYY-MM-DD pattern at end)
        # Last 3 parts are year-month-day
        date_str = '-'.join(slug_parts[-3:])

        # Team names are between sport and date
        team_parts = slug_parts[1:-3]

        # Split teams (try to find middle point)
        # This is tricky - Polymarket may have team names with hyphens
        # Use game_date from market data as authoritative source

        # Simpler approach: Use the market data we already have
        # Extract from the slug or use a different method

        # For now, let's fetch price using market_id directly
        # We'll need to modify get_current_price to accept market_id

        # Alternative: Parse slug more carefully
        # NFL teams are typically 1 word abbreviations
        # NBA teams are 2-4 letter abbreviations

        # Let's reconstruct from market data
        sport = market['sport'].lower()
        game_date = market['game_date']

        # For simplicity, extract from slug
        # Assuming format: sport-away-home-YYYY-MM-DD
        # We need to handle multi-word team names

        # Better approach: Use market_id to fetch price directly
        # But Polymarket API requires slug format

        # Use the polymarket_slug directly with a new helper function
        current_price = await get_price_by_slug(session, market['polymarket_slug'])

        if current_price and current_price.get('away_price') is not None:
            # Store price snapshot
            now = datetime.now(ZoneInfo("UTC"))
            success = db.insert_price_snapshot(
                market_id=market['market_id'],
                timestamp=now,
                away_price=current_price['away_price'],
                home_price=current_price['home_price']
            )

            if success:
                print(f"  ✓ {market['polymarket_slug']}: away={current_price['away_price']:.3f}, home={current_price['home_price']:.3f}")
                return True
            else:
                print(f"  ✗ Failed to store: {market['polymarket_slug']}")
                return False
        else:
            print(f"  ✗ No price data: {market['polymarket_slug']}")
            return False

    except Exception as e:
        print(f"  ✗ Error tracking {market.get('polymarket_slug', 'unknown')}: {e}")
        return False


async def get_price_by_slug(session: aiohttp.ClientSession, slug: str) -> dict:
    """
    Get current price for a market using its slug directly.

    Args:
        session: aiohttp session
        slug: Polymarket slug (e.g., "nfl-giants-broncos-2024-11-08")

    Returns:
        Dict with away_price, home_price, timestamp or empty dict on error
    """
    try:
        market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        price_url = "https://clob.polymarket.com/prices-history"

        # Get market metadata
        async with polymarket_api._polymarket_semaphore:
            data = await polymarket_api._rate_limited_get(session, market_url)

            import json
            clobIdTokens = json.loads(data["clobTokenIds"])

            # Get current price (last 2 minutes)
            now_ts = int(datetime.now().timestamp())
            start_ts = now_ts - 120

            queryString = {
                "market": clobIdTokens[0],
                "startTs": start_ts,
                "endTs": now_ts
            }

            info = await polymarket_api._rate_limited_get(session, price_url, params=queryString)

            if not info.get("history"):
                return {}

            # Get most recent price
            price_first = info["history"][-1]["p"]
            price_second = 1.0 - price_first

            return {
                "away_price": price_first,
                "home_price": price_second,
                "timestamp": now_ts
            }

    except Exception as e:
        print(f"    Error fetching price for {slug}: {e}")
        return {}


async def main():
    """Main entry point for price tracking."""
    print("=" * 60)
    print("Market Price Tracking Service")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)

    # Get all active markets from database
    active_markets = db.get_active_markets(status='open')

    if not active_markets:
        print("No active markets to track")
        print("=" * 60)
        return

    print(f"Tracking {len(active_markets)} active markets...")
    print()

    async with aiohttp.ClientSession() as session:
        # Track all markets concurrently (with rate limiting handled by polymarket_api)
        tasks = [track_market_price(session, market) for market in active_markets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Summary
    successful = sum(1 for r in results if r is True)
    failed = len(results) - successful

    print()
    print(f"Summary: {successful} successful, {failed} failed")
    print(f"Completed at: {datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
