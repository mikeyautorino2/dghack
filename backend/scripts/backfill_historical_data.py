#!/usr/bin/env python3
"""
Historical Data Backfill Script

Backfills database with historical game data from:
- NBA: Oct 18, 2022 onwards
- NFL: Week 1 2023 onwards (actually Week 4+ due to API constraint)
- MLB: May 1, 2022 onwards (Jan 1 requested, but API only allows May 1+)

Usage:
    python backend/scripts/backfill_historical_data.py
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
from datetime import date, datetime
from tqdm import tqdm
from sqlalchemy import text
from backend.services import basketball_api, football_api, baseball_api
from backend.app.db import insert_nba_games, insert_nfl_games, insert_mlb_games, engine


# ============================================================================
# DATABASE CONNECTION TEST
# ============================================================================

def test_database_connection():
    """Test database connection before starting backfill."""
    print("\n" + "=" * 70)
    print("DATABASE CONNECTION TEST")
    print("=" * 70)

    try:
        # Test connection with a simple query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        # Get database URL for display (hide password)
        db_url = str(engine.url)
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
        print("=" * 70 + "\n")
        return True

    except Exception as e:
        print(f"✗ Failed to connect to database")
        print(f"  Error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL in .env is correct")
        print("  3. Database exists and user has access")
        print("=" * 70 + "\n")
        return False


# ============================================================================
# NBA BACKFILL
# ============================================================================

async def backfill_nba():
    """
    Backfill NBA data from Oct 18, 2022 through current season.

    NBA seasons span October through June.
    """
    print("=" * 70)
    print("NBA DATA BACKFILL")
    print("=" * 70)

    # Define NBA seasons to backfill
    # Format: (start_date, end_date, season_label)
    seasons = [
        (date(2022, 10, 18), date(2023, 6, 30), "2022-23"),
        (date(2023, 10, 1), date(2024, 6, 30), "2023-24"),
        (date(2024, 10, 1), date(2024, 11, 8), "2024-25 (current)"),  # Up to today
    ]

    total_games = 0

    # Progress bar for seasons
    season_progress = tqdm(seasons, desc="NBA Seasons", unit="season")

    for start_date, end_date, label in season_progress:
        season_progress.set_description(f"NBA {label}")

        try:
            # Fetch data from API (async)
            df = await basketball_api.get_matchups_cumulative_stats_between(
                start_date=start_date,
                end_date=end_date,
                season_type="Regular Season"
            )

            if df.empty:
                tqdm.write(f"  ⚠️  No games found for {label}")
                continue

            # Insert into database
            rows = insert_nba_games(df)
            total_games += rows
            tqdm.write(f"  ✓ Inserted {rows} games for {label}")

        except Exception as e:
            tqdm.write(f"  ✗ Error fetching {label}: {e}")
            continue

    print(f"\n{'─' * 70}")
    print(f"NBA COMPLETE: {total_games} total games inserted")
    print(f"{'─' * 70}\n")


# ============================================================================
# NFL BACKFILL
# ============================================================================

async def backfill_nfl():
    """
    Backfill NFL data from Week 1 2023 onwards.

    Note: API only returns games from Week 4+ (needs weeks 1-3 for cumulative stats)
    NFL seasons run September through February (18 weeks regular season)
    """
    print("=" * 70)
    print("NFL DATA BACKFILL")
    print("=" * 70)

    # Define NFL seasons to backfill
    # Format: (start_week, start_year, end_week, end_year, season_label)
    # Note: API filters to week 4+ automatically
    seasons = [
        (1, 2023, 18, 2023, "2023"),    # Actually fetches weeks 4-18
        (1, 2024, 18, 2024, "2024"),    # Actually fetches weeks 4-current
    ]

    total_games = 0

    # Progress bar for seasons
    season_progress = tqdm(seasons, desc="NFL Seasons", unit="season")

    for start_week, start_year, end_week, end_year, label in season_progress:
        season_progress.set_description(f"NFL {label}")
        tqdm.write(f"  (Note: API automatically filters to Week 4+ only)")

        try:
            # Fetch data from API (async)
            df = await football_api.get_historical_data(
                start_week=start_week,
                start_year=start_year,
                end_week=end_week,
                end_year=end_year,
                fetch_market_data=True
            )

            if df.empty:
                tqdm.write(f"  ⚠️  No games found for {label}")
                continue

            # Insert into database
            rows = insert_nfl_games(df)
            total_games += rows
            tqdm.write(f"  ✓ Inserted {rows} games for {label}")

        except Exception as e:
            tqdm.write(f"  ✗ Error fetching {label}: {e}")
            continue

    print(f"\n{'─' * 70}")
    print(f"NFL COMPLETE: {total_games} total games inserted")
    print(f"{'─' * 70}\n")


# ============================================================================
# MLB BACKFILL
# ============================================================================

async def backfill_mlb():
    """
    Backfill MLB data from May 1, 2022 onwards.

    Note: User requested Jan 1, 2022 but API only accepts games from May 1st onwards.
    MLB seasons run April through October.
    """
    print("=" * 70)
    print("MLB DATA BACKFILL")
    print("=" * 70)
    print("Note: User requested Jan 1, 2022, but API only allows May 1+")

    # Define MLB seasons to backfill
    # Format: (start_date, end_date, season_label)
    seasons = [
        (date(2022, 5, 1), date(2022, 10, 31), "2022"),
        (date(2023, 5, 1), date(2023, 10, 31), "2023"),
        (date(2024, 5, 1), date(2024, 10, 31), "2024"),
    ]

    total_games = 0

    # Progress bar for seasons
    season_progress = tqdm(seasons, desc="MLB Seasons", unit="season")

    for start_date, end_date, label in season_progress:
        season_progress.set_description(f"MLB {label}")

        try:
            # Fetch data from API (async)
            df = await baseball_api.get_historical_data(
                start_date=start_date,
                end_date=end_date,
                fetch_market_data=True
            )

            if df.empty:
                tqdm.write(f"  ⚠️  No games found for {label}")
                continue

            # Insert into database
            rows = insert_mlb_games(df)
            total_games += rows
            tqdm.write(f"  ✓ Inserted {rows} games for {label}")

        except Exception as e:
            tqdm.write(f"  ✗ Error fetching {label}: {e}")
            continue

    print(f"\n{'─' * 70}")
    print(f"MLB COMPLETE: {total_games} total games inserted")
    print(f"{'─' * 70}\n")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point - runs all backfills sequentially."""

    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  HISTORICAL DATA BACKFILL SCRIPT".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()
    print("This script will backfill historical game data for:")
    print("  • NBA: Oct 18, 2022 → Present")
    print("  • NFL: Week 1 2023 → Present (Week 4+ only, API constraint)")
    print("  • MLB: May 1, 2022 → Present (API constraint: no games before May 1)")
    print()
    print("Note: This may take several minutes due to API rate limiting.")
    print("*" * 70)
    print()

    # Test database connection first
    if not test_database_connection():
        print("✗ Aborting: Cannot connect to database")
        sys.exit(1)

    start_time = datetime.now()

    # Overall progress bar for all sports
    sports = ['NFL', 'MLB', 'NBA']
    overall_progress = tqdm(total=len(sports), desc="Overall Progress", unit="sport", position=0)

    try:
        # Run NFL backfill (async)
        await backfill_nfl()
        overall_progress.update(1)

        # Run MLB backfill (async)
        await backfill_mlb()
        overall_progress.update(1)

        # Run NBA backfill (async)
        await backfill_nba()
        overall_progress.update(1)

        overall_progress.close()

    except KeyboardInterrupt:
        overall_progress.close()
        print("\n\n⚠️  Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        overall_progress.close()
        print(f"\n\n✗ Fatal error during backfill: {e}")
        sys.exit(1)

    # Summary
    elapsed = datetime.now() - start_time
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  BACKFILL COMPLETE".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print(f"\nTotal time: {elapsed}")
    print("\nYou can now query the database to verify the data was inserted.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
