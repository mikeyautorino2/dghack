#!/usr/bin/env python3
"""
NFL Historical Data Backfill Script

Backfills database with historical NFL game data from Week 1 2023 onwards.
Note: API only returns games from Week 4+ (needs weeks 1-3 for cumulative stats)

Usage:
    python backend/scripts/backfill_historical_data.py
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
from datetime import datetime
from sqlalchemy import text
from backend.services import football_api, basketball_api
from backend.app.db import insert_nfl_games, insert_nba_games, engine


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
# NFL BACKFILL
# ============================================================================

async def backfill_nfl():
    """
    Backfill NFL data from Week 1 2023 through Week 18 2024.

    Note: API only returns games from Week 4+ (needs weeks 1-3 for cumulative stats)
    NFL seasons run September through February (18 weeks regular season)
    """
    print("=" * 70)
    print("NFL DATA BACKFILL")
    print("=" * 70)
    print("\nFetching NFL data from 2023 Week 1 through 2024 Week 18...")
    print("(Note: API automatically filters to Week 4+ only)")

    try:
        # Fetch data from API (async) - one call handles multiple seasons
        START_WEEK = 1
        START_YEAR = 2023
        END_WEEK = 18
        END_YEAR = 2025
        
        df = await football_api.get_historical_data(
            start_week=START_WEEK,
            start_year=START_YEAR,
            end_week=END_WEEK,
            end_year=END_YEAR,
            fetch_market_data=True
        )

        if df.empty:
            print("  ⚠️  No games found")
            return

        # Insert into database
        rows = insert_nfl_games(df)
        print(f"\n✓ Successfully inserted {rows} games")

    except Exception as e:
        print(f"\n✗ Error fetching NFL data: {e}")
        raise

    print(f"\n{'─' * 70}")
    print(f"NFL BACKFILL COMPLETE: {rows} total games inserted")
    print(f"{'─' * 70}\n")


# ============================================================================
# NBA BACKFILL
# ============================================================================

async def backfill_nba():
    """
    Backfill NBA data from 2023-24 season through 2024-25 season.

    Note: NBA seasons run October through June (82 games regular season)
    Season spans two calendar years (e.g., 2024 = 2023-24 season is Oct 2023 - June 2024)
    """
    print("=" * 70)
    print("NBA DATA BACKFILL")
    print("=" * 70)
    print("\nFetching NBA data from 2023-24 season through 2024-25 season...")

    try:
        # Fetch data from API (async)
        # 2024 = 2023-24 season (Oct 2023 - June 2024)
        # 2025 = 2024-25 season (Oct 2024 - June 2025)
        START_SEASON = 2023
        END_SEASON = 2025

        df = await basketball_api.get_historical_data(
            start_season=START_SEASON,
            end_season=END_SEASON,
            fetch_market_data=True
        )

        if df.empty:
            print("  ⚠️  No games found")
            return

        # Insert into database
        rows = insert_nba_games(df)
        print(f"\n✓ Successfully inserted {rows} games")

    except Exception as e:
        print(f"\n✗ Error fetching NBA data: {e}")
        raise

    print(f"\n{'─' * 70}")
    print(f"NBA BACKFILL COMPLETE: {rows} total games inserted")
    print(f"{'─' * 70}\n")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point - runs NFL backfill."""

    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  NFL HISTORICAL DATA BACKFILL SCRIPT".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()
    print("This script will backfill historical NFL game data:")
    print("  • NFL: Week 1 2023 → Present (Week 4+ only, API constraint)")
    print()
    print("Note: This may take several minutes due to API rate limiting.")
    print("*" * 70)
    print()

    # Test database connection first
    if not test_database_connection():
        print("✗ Aborting: Cannot connect to database")
        sys.exit(1)

    start_time = datetime.now()

    try:
        # Run NFL backfill (async)
        await backfill_nfl()

    except KeyboardInterrupt:
        print("\n\n⚠️  Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
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
