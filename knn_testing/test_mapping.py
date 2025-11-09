#!/usr/bin/env python3
"""Test script to verify team mapping logic."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, NFLGameFeatures
from app.services.knn_service import find_similar_games


def test_mapping():
    """Test team mapping by comparing statistics."""
    db = SessionLocal()

    try:
        # Get a sample game
        sample_game = db.query(NFLGameFeatures).first()
        if not sample_game:
            print("No NFL games found in database")
            return False

        print("=" * 80)
        print("TESTING TEAM MAPPING")
        print("=" * 80)

        print(f"\nQUERY GAME:")
        print(f"  {sample_game.away_team} @ {sample_game.home_team}")
        print(f"  Date: {sample_game.game_date}")
        print(f"  Game ID: {sample_game.game_id}")

        print(f"\n  HOME TEAM ({sample_game.home_team}) STATS:")
        print(f"    Yards/Play: {sample_game.home_yardsPerPlay:.2f}")
        print(f"    3rd Down Eff: {sample_game.home_thirdDownEff:.3f}")
        print(f"    First Downs: {sample_game.home_firstDowns:.1f}")

        print(f"\n  AWAY TEAM ({sample_game.away_team}) STATS:")
        print(f"    Yards/Play: {sample_game.away_yardsPerPlay:.2f}")
        print(f"    3rd Down Eff: {sample_game.away_thirdDownEff:.3f}")
        print(f"    First Downs: {sample_game.away_firstDowns:.1f}")

        # Find similar games
        print(f"\n{'='*80}")
        print("SIMILAR GAMES WITH MAPPING")
        print("=" * 80)

        results = find_similar_games(db, 'NFL', sample_game.game_id, k=3)

        if not results:
            print("No similar games found")
            return False

        for i, result in enumerate(results, 1):
            # Fetch the similar game details
            similar_game = db.query(NFLGameFeatures).filter_by(
                game_id=result['game_id']
            ).first()

            if not similar_game:
                continue

            print(f"\n{i}. SIMILAR GAME:")
            print(f"   {result['away']} @ {result['home']}")
            print(f"   Date: {result['date']}")
            print(f"   Similarity: {result['similarity']}%")
            print(f"   Mapping: {result['mapping']}")

            print(f"\n   HISTORICAL HOME ({result['home']}) STATS:")
            print(f"     Yards/Play: {similar_game.home_yardsPerPlay:.2f}")
            print(f"     3rd Down Eff: {similar_game.home_thirdDownEff:.3f}")
            print(f"     First Downs: {similar_game.home_firstDowns:.1f}")

            print(f"\n   HISTORICAL AWAY ({result['away']}) STATS:")
            print(f"     Yards/Play: {similar_game.away_yardsPerPlay:.2f}")
            print(f"     3rd Down Eff: {similar_game.away_thirdDownEff:.3f}")
            print(f"     First Downs: {similar_game.away_firstDowns:.1f}")

            # Validate mapping
            print(f"\n   MAPPING INTERPRETATION:")
            if result['mapping'] == 'direct':
                print(f"     Current HOME ({sample_game.home_team}) corresponds to Historical HOME ({result['home']})")
                print(f"     Current AWAY ({sample_game.away_team}) corresponds to Historical AWAY ({result['away']})")

                # Compare stats to validate
                home_diff = abs(sample_game.home_yardsPerPlay - similar_game.home_yardsPerPlay)
                away_diff = abs(sample_game.away_yardsPerPlay - similar_game.away_yardsPerPlay)
                print(f"\n     Yards/Play difference (direct):")
                print(f"       Home: {home_diff:.2f}")
                print(f"       Away: {away_diff:.2f}")
                print(f"       Total: {home_diff + away_diff:.2f}")

            else:  # flipped
                print(f"     Current HOME ({sample_game.home_team}) corresponds to Historical AWAY ({result['away']})")
                print(f"     Current AWAY ({sample_game.away_team}) corresponds to Historical HOME ({result['home']})")

                # Compare stats to validate
                home_diff = abs(sample_game.home_yardsPerPlay - similar_game.away_yardsPerPlay)
                away_diff = abs(sample_game.away_yardsPerPlay - similar_game.home_yardsPerPlay)
                print(f"\n     Yards/Play difference (flipped):")
                print(f"       Current Home vs Historical Away: {home_diff:.2f}")
                print(f"       Current Away vs Historical Home: {away_diff:.2f}")
                print(f"       Total: {home_diff + away_diff:.2f}")

            print(f"\n   {'-'*76}")

        print("\n" + "=" * 80)
        print("✓ Mapping test completed")
        print("  Review the stats above to verify mapping makes sense")
        print("  Lower 'Total' difference indicates better mapping choice")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = test_mapping()
    sys.exit(0 if success else 1)
