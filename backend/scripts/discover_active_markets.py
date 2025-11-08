#!/usr/bin/env python3
"""
Market Discovery Service

Discovers upcoming NBA and NFL games and checks if Polymarket markets exist for them.
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

# Import service APIs
from backend.services import polymarket_api
from backend.services.football_api import TEAM_ID_MAP as NFL_TEAM_MAP
from backend.app import db


async def discover_nfl_markets(session: aiohttp.ClientSession, days_ahead: int = 30) -> list[dict]:
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


async def discover_nba_markets(session: aiohttp.ClientSession, days_ahead: int = 30) -> list[dict]:
    """
    Discover upcoming NBA games and check for Polymarket markets.

    Args:
        session: aiohttp session
        days_ahead: How many days ahead to look for games

    Returns:
        List of market dicts ready for insertion
    """
    print("Discovering NBA markets...")
    markets = []

    try:
        from nba_api.stats.static import teams
        from nba_api.stats.endpoints import leaguegamefinder
        import time

        # Get all NBA teams
        nba_teams = teams.get_teams()
        team_dict = {team['id']: team for team in nba_teams}

        # Get current season (e.g., "2024-25")
        today = datetime.now(ZoneInfo("America/New_York"))
        if today.month >= 10:  # Oct-Dec
            season_year = today.year
        else:  # Jan-Sep
            season_year = today.year - 1

        season = f"{season_year}-{str(season_year + 1)[-2:]}"

        # Query NBA API for upcoming games (use schedule endpoint or web scraping)
        # Note: nba_api doesn't have a great "future games" endpoint
        # Alternative: scrape from ESPN or NBA.com

        # For now, use ESPN NBA API as fallback
        end_date = (today + timedelta(days=days_ahead)).date()
        current_date = today.date()

        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            url = f"https://cdn.espn.com/core/nba/schedule?xhr=1&date={date_str}"

            try:
                await asyncio.sleep(0.5)  # Rate limit
                async with session.get(url) as response:
                    if response.status != 200:
                        current_date += timedelta(days=1)
                        continue

                    data = await response.json()
                    events = data.get("content", {}).get("schedule", {}).values()

                    for date_data in events:
                        games = date_data.get("games", [])

                        for game in games:
                            try:
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
                                game_date = game_datetime_utc.date()

                                away_name = away_team.get("team", {}).get("displayName", "")
                                home_name = home_team.get("team", {}).get("displayName", "")

                                # Convert to Polymarket abbreviations (lowercase)
                                # This is a simplified mapping - may need refinement
                                away_abbrev = away_team.get("team", {}).get("abbreviation", "").lower()
                                home_abbrev = home_team.get("team", {}).get("abbreviation", "").lower()

                                if not away_abbrev or not home_abbrev:
                                    continue

                                # Check if Polymarket market exists
                                market_info = await polymarket_api.check_market_exists(
                                    session,
                                    sport="nba",
                                    date=game_date,
                                    away_team=away_abbrev,
                                    home_team=home_abbrev
                                )

                                if market_info.get("exists"):
                                    markets.append({
                                        "market_id": market_info["market_id"],
                                        "polymarket_slug": market_info["polymarket_slug"],
                                        "sport": "NBA",
                                        "game_date": game_date,
                                        "away_team": away_name,
                                        "away_team_id": away_team.get("id"),
                                        "home_team": home_name,
                                        "home_team_id": home_team.get("id"),
                                        "game_start_ts": market_info["game_start_ts"],
                                        "market_open_ts": market_info.get("market_open_ts"),
                                        "market_close_ts": market_info.get("market_close_ts"),
                                        "market_status": "open"
                                    })
                                    print(f"  Found: {away_abbrev} @ {home_abbrev} on {game_date}")

                            except Exception as e:
                                print(f"  Error processing NBA game {event_id}: {e}")
                                continue

            except Exception as e:
                print(f"  Error fetching NBA games for {current_date}: {e}")

            current_date += timedelta(days=1)

    except ImportError:
        print("  nba_api not available, skipping NBA discovery")

    print(f"Found {len(markets)} NBA markets")
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
        now = datetime.now(timezone.utc)

        # Get all open markets
        open_markets = session.query(db.ActiveMarket).filter_by(market_status='open').all()

        for market in open_markets:
            # If game has started and market close time has passed, mark as closed
            if market.game_start_ts and market.game_start_ts < now:
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
    print("Market Discovery Service")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Discover markets for both sports
        nfl_markets = await discover_nfl_markets(session, days_ahead=30)
        nba_markets = await discover_nba_markets(session, days_ahead=30)

        all_markets = nfl_markets + nba_markets

        if all_markets:
            print(f"\nInserting {len(all_markets)} markets into database...")
            try:
                inserted = db.insert_active_markets(all_markets)
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
