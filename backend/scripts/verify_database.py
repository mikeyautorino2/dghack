#!/usr/bin/env python3
"""
Database Verification Script

Checks how many games are stored in the database for each sport.

Usage:
    python backend/scripts/verify_database.py
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.db import SessionLocal, NBAGameFeatures, NFLGameFeatures, MLBGameFeatures
from sqlalchemy import func


def verify_database():
    """Query database and display statistics."""

    print("\n" + "=" * 70)
    print("DATABASE VERIFICATION")
    print("=" * 70 + "\n")

    session = SessionLocal()

    try:
        # NBA Statistics
        print("NBA (nba_games_features)")
        print("-" * 70)

        nba_count = session.query(NBAGameFeatures).count()
        print(f"  Total games: {nba_count}")

        if nba_count > 0:
            # Get season breakdown
            nba_by_season = session.query(
                NBAGameFeatures.season,
                func.count(NBAGameFeatures.game_id)
            ).group_by(NBAGameFeatures.season).order_by(NBAGameFeatures.season).all()

            print(f"  Breakdown by season:")
            for season, count in nba_by_season:
                season_label = f"{season}-{str(season+1)[2:]}" if season else "Unknown"
                print(f"    {season_label}: {count} games")

            # Date range
            first_game = session.query(func.min(NBAGameFeatures.game_date)).scalar()
            last_game = session.query(func.max(NBAGameFeatures.game_date)).scalar()
            print(f"  Date range: {first_game} to {last_game}")

        print()

        # NFL Statistics
        print("NFL (nfl_games_features)")
        print("-" * 70)

        nfl_count = session.query(NFLGameFeatures).count()
        print(f"  Total games: {nfl_count}")

        if nfl_count > 0:
            # Get season breakdown
            nfl_by_season = session.query(
                NFLGameFeatures.season,
                func.count(NFLGameFeatures.game_id)
            ).group_by(NFLGameFeatures.season).order_by(NFLGameFeatures.season).all()

            print(f"  Breakdown by season:")
            for season, count in nfl_by_season:
                print(f"    {season}: {count} games")

            # Week range
            min_week = session.query(func.min(NFLGameFeatures.week)).scalar()
            max_week = session.query(func.max(NFLGameFeatures.week)).scalar()
            print(f"  Week range: Week {min_week} to Week {max_week}")

            # Date range
            first_game = session.query(func.min(NFLGameFeatures.game_date)).scalar()
            last_game = session.query(func.max(NFLGameFeatures.game_date)).scalar()
            print(f"  Date range: {first_game} to {last_game}")

        print()

        # MLB Statistics
        print("MLB (mlb_games_features)")
        print("-" * 70)

        mlb_count = session.query(MLBGameFeatures).count()
        print(f"  Total games: {mlb_count}")

        if mlb_count > 0:
            # Get season breakdown
            mlb_by_season = session.query(
                MLBGameFeatures.season,
                func.count(MLBGameFeatures.game_id)
            ).group_by(MLBGameFeatures.season).order_by(MLBGameFeatures.season).all()

            print(f"  Breakdown by season:")
            for season, count in mlb_by_season:
                print(f"    {season}: {count} games")

            # Date range
            first_game = session.query(func.min(MLBGameFeatures.game_date)).scalar()
            last_game = session.query(func.max(MLBGameFeatures.game_date)).scalar()
            print(f"  Date range: {first_game} to {last_game}")

        print()

        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        total = nba_count + nfl_count + mlb_count
        print(f"  Total games in database: {total}")
        print(f"    • NBA: {nba_count}")
        print(f"    • NFL: {nfl_count}")
        print(f"    • MLB: {mlb_count}")
        print()

    except Exception as e:
        print(f"✗ Error querying database: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    try:
        verify_database()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}\n")
        sys.exit(1)
