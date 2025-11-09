#!/usr/bin/env python3
"""Test script to verify normalization bug fix."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, NFLGameFeatures
from app.services.knn_service import find_similar_games


def test_normalization_fix():
    """Test absolute normalization: no 100% or 0% extremes, consistent scores across k."""
    db = SessionLocal()

    try:
        # Get a sample game
        sample_game = db.query(NFLGameFeatures).first()
        if not sample_game:
            print("No NFL games found in database")
            return False

        print("=" * 60)
        print("TESTING ABSOLUTE NORMALIZATION FIX")
        print("=" * 60)
        print(f"\nTarget Game: {sample_game.away_team} @ {sample_game.home_team}")
        print(f"Game ID: {sample_game.game_id}")
        print("\nExpected behavior with absolute normalization:")
        print("  - No non-query game should have 100% similarity")
        print("  - No game should have exactly 0% (unless dist > 2.0)")
        print("  - Same game should have same score regardless of k")

        # Store results from all k values
        all_results = {}

        # Test with different k values
        for k in [1, 4, 10]:
            print(f"\n{'='*60}")
            print(f"Testing with k={k}")
            print(f"{'='*60}")

            results = find_similar_games(db, 'NFL', sample_game.game_id, k=k)

            if not results:
                print(f"  ✗ No results returned for k={k}")
                continue

            print(f"  Found {len(results)} games:")
            for i, game in enumerate(results, 1):
                game_key = game['game_id']
                print(f"  {i}. {game['away']} @ {game['home']}")
                print(f"     Similarity: {game['similarity']}%")

                # Store for consistency check
                if game_key not in all_results:
                    all_results[game_key] = []
                all_results[game_key].append((k, game['similarity']))

            # Validate results
            top_similarity = results[0]['similarity']
            last_similarity = results[-1]['similarity']

            # Check: no 100% similarity (unless it's the query game itself, which shouldn't be in results)
            if top_similarity == 100:
                print(f"\n  ✗ FAIL: Top game has 100% similarity (should be < 100% with absolute normalization)")
                return False

            # Check: top similarity should be reasonable (typically 60-85% for closest neighbor)
            if top_similarity < 30 or top_similarity > 90:
                print(f"\n  ⚠ WARNING: Top similarity is {top_similarity}% (expected 60-85%)")
            else:
                print(f"\n  ✓ PASS: Top similarity is {top_similarity}% (reasonable range)")

            # Check: last game should not be exactly 0% (unless very dissimilar)
            if k > 1 and last_similarity == 0:
                print(f"  ⚠ WARNING: Last game has 0% similarity (may be very dissimilar)")

        # Check consistency across k values
        print(f"\n{'='*60}")
        print("CHECKING CONSISTENCY ACROSS K VALUES")
        print(f"{'='*60}")

        consistent = True
        for game_id, scores in all_results.items():
            if len(scores) > 1:
                # Get unique similarities for this game across different k values
                similarities = [s for _, s in scores]
                if len(set(similarities)) > 1:
                    print(f"\n✗ INCONSISTENT: Game {game_id}")
                    for k, sim in scores:
                        print(f"  k={k}: {sim}%")
                    consistent = False

        if consistent:
            print("\n✓ PASS: Similarity scores are consistent across different k values")
        else:
            print("\n✗ FAIL: Similarity scores vary with k (should be absolute)")
            return False

        print("\n" + "=" * 60)
        print("✓ All tests passed - absolute normalization is working!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = test_normalization_fix()
    sys.exit(0 if success else 1)
