#!/usr/bin/env python3
"""
Market Discovery Service

Discovers upcoming NFL games and checks if Polymarket markets exist for them.
Stores active markets in the database for continuous price tracking.

Run frequency: Every 6 hours via cron
(Markets typically open ~1 day before games)
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import aiohttp
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from sqlalchemy import text

# Import service APIs
from backend.services import polymarket_api
from backend.services.football_api import TEAM_ID_MAP as NFL_TEAM_MAP
from backend.app import db


# ============================================================================
# DATABASE CONNECTION TEST
# ============================================================================

def test_database_connection():
    """Test database connection before starting discovery."""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)

    try:
        # Test connection with a simple query
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        # Get database URL for display (hide password)
        db_url = str(db.engine.url)
        if '@' in db_url and ':' in db_url:
            # Format: postgresql://user:password@host:port/database
            parts = db_url.split('@')
            user_part = parts[0].split(':')[0]  # Get user without password
            host_part = '@'.join(parts[1:])
            display_url = f"{user_part}:****@{host_part}"
        else:
            display_url = db_url

        print(f"✓ Successfully connected to database")
        print(f"  URL: {display_url}")
        print("=" * 60 + "\n")
        return True

    except Exception as e:
        print(f"✗ Failed to connect to database")
        print(f"  Error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL in .env is correct")
        print("  3. Database exists and user has access")
        print("=" * 60 + "\n")
        return False


# ============================================================================
# MARKET DISCOVERY
# ============================================================================

async def discover_nfl_markets(session: aiohttp.ClientSession, days_ahead: int = 10) -> list[dict]:
    """
    Discover upcoming NFL games and check for Polymarket markets.

    Args:
        session: aiohttp session
        days_ahead: How many days ahead to look for games

    Returns:
        List of market dicts ready for insertion
    """
    print("Discovering NFL markets...")
    markets = []

    # Query ESPN API for upcoming NFL games
    # Get current week and year
    today = datetime.now(ZoneInfo("America/New_York"))
    current_year = today.year

    # NFL season: Sept-Feb (weeks 1-18 + playoffs)
    # Simple heuristic: check current week through next 4 weeks
    for week_offset in range(5):
        # Estimate current week (rough approximation)
        # Week 1 typically starts first week of September
        week = min(18, 1 + (today.timetuple().tm_yday - 245) // 7 + week_offset)

        url = f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={current_year}&week={week}"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    continue

                data = await response.json()
                events = data.get("content", {}).get("schedule", {}).values()

                for week_data in events:
                    games = week_data.get("games", [])

                    for game in games:
                        try:
                            # Extract game info
                            event_id = game.get("id")
                            competition = game.get("competitions", [{}])[0]
                            competitors = competition.get("competitors", [])

                            home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
                            away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)

                            if not home_team or not away_team:
                                continue

                            # Parse game date
                            game_date_str = game.get("date")
                            game_datetime_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                            game_datetime_et = game_datetime_utc.astimezone(ZoneInfo("America/New_York"))
                            game_date = game_datetime_et.date()

                            # Skip past games or games too far in future
                            days_until = (game_date - today.date()).days
                            if days_until < 0 or days_until > days_ahead:
                                continue

                            away_id = int(away_team["id"])
                            home_id = int(home_team["id"])

                            # Get Polymarket team names from mapping
                            away_poly = NFL_TEAM_MAP.get(away_id, (None, None, None))[2]
                            home_poly = NFL_TEAM_MAP.get(home_id, (None, None, None))[2]

                            if not away_poly or not home_poly:
                                continue

                            # Check if Polymarket market exists
                            market_info = await polymarket_api.check_market_exists(
                                session,
                                sport="nfl",
                                date=game_date,
                                away_team=away_poly,
                                home_team=home_poly
                            )

                            if market_info.get("exists"):
                                markets.append({
                                    "market_id": market_info["market_id"],
                                    "polymarket_slug": market_info["polymarket_slug"],
                                    "sport": "NFL",
                                    "game_date": game_date,
                                    "away_team": away_team.get("team", {}).get("displayName", "Unknown"),
                                    "away_team_id": str(away_id),
                                    "home_team": home_team.get("team", {}).get("displayName", "Unknown"),
                                    "home_team_id": str(home_id),
                                    "game_start_ts": market_info["game_start_ts"],
                                    "market_open_ts": market_info.get("market_open_ts"),
                                    "market_close_ts": market_info.get("market_close_ts"),
                                    "market_status": "open"
                                })
                                print(f"  Found: {away_poly} @ {home_poly} on {game_date}")

                        except Exception as e:
                            print(f"  Error processing NFL game {event_id}: {e}")
                            continue

        except Exception as e:
            print(f"  Error fetching NFL week {week}: {e}")
            continue

    print(f"Found {len(markets)} NFL markets")
    return markets


async def cleanup_old_markets():
    """
    Remove markets that have been resolved or are past their game time.
    Update status of closed markets.
    """
    print("Cleaning up old markets...")

    from datetime import timezone

    session = db.SessionLocal()
    try:
        now_ts = int(datetime.now(timezone.utc).timestamp())

        # Get all open markets
        open_markets = session.query(db.ActiveMarket).filter_by(market_status='open').all()

        for market in open_markets:
            # If game has started, mark as closed
            if market.game_start_ts and market.game_start_ts < now_ts:
                # Game has started, mark as closed
                market.market_status = 'closed'
                print(f"  Marked as closed: {market.polymarket_slug}")

        session.commit()
        print("Cleanup complete")

    except Exception as e:
        session.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        session.close()


async def main():
    """Main entry point for market discovery."""
    print("=" * 60)
    print("NFL Market Discovery Service")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)

    # Test database connection first
    if not test_database_connection():
        print("✗ Aborting: Cannot connect to database")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        # Discover NFL markets
        nfl_markets = await discover_nfl_markets(session, days_ahead=10)

        if nfl_markets:
            print(f"\nInserting {len(nfl_markets)} markets into database...")
            try:
                inserted = db.insert_active_markets(nfl_markets)
                print(f"Successfully inserted {inserted} new markets")
            except Exception as e:
                print(f"Error inserting markets: {e}")
        else:
            print("No new markets found")

    # Cleanup old markets
    await cleanup_old_markets()

    print("\nDiscovery complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
