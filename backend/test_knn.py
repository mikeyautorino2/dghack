#!/usr/bin/env python3
"""Test script for KNN similarity search."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, NBAGameFeatures, NFLGameFeatures
from app.services.knn_service import find_similar_games


def test_sport(db, sport: str):
    """Test KNN for a specific sport."""
    print("\n" + "=" * 60)
    print(f"TESTING {sport}")
    print("=" * 60)

    # Get model
    model = NBAGameFeatures if sport == 'NBA' else NFLGameFeatures

    # Get sample game
    sample_game = db.query(model).first()

    if not sample_game:
        print(f"No {sport} games found in database")
        return False

    print("\nTARGET GAME")
    print("-" * 60)
    print(f"ID: {sample_game.game_id}")
    print(f"Date: {sample_game.game_date}")
    print(f"Matchup: {sample_game.away_team} @ {sample_game.home_team}")

    if sport == 'NBA':
        print(f"Stats: {sample_game.home_avg_pts:.1f} - {sample_game.away_avg_pts:.1f} pts")
        print(f"       {sample_game.home_fg_pct:.3f} - {sample_game.away_fg_pct:.3f} FG%")
    else:  # NFL
        print(f"Stats: {sample_game.home_yardsPerPlay:.2f} - {sample_game.away_yardsPerPlay:.2f} yds/play")
        print(f"       {sample_game.home_thirdDownEff:.3f} - {sample_game.away_thirdDownEff:.3f} 3rd down")

    print("\nFinding similar games (using symmetric features by default)...")

    # Find similar games (default: use_symmetric=True)
    results = find_similar_games(db, sport, sample_game.game_id, k=10)

    if not results:
        print("No similar games found")
        return False

    print(f"\nFound {len(results)} similar games:\n")

    for i, game in enumerate(results, 1):
        print(f"{i}. {game['away']} @ {game['home']}")
        print(f"   Date: {game['date']}")
        print(f"   Similarity: {game['similarity']}%\n")

    return True


def test_symmetry(db, sport: str):
    """Test home/away symmetry feature."""
    print("\n" + "=" * 60)
    print(f"TESTING {sport} SYMMETRY")
    print("=" * 60)

    model = NBAGameFeatures if sport == 'NBA' else NFLGameFeatures

    # Get a random game
    sample_game = db.query(model).first()
    if not sample_game:
        print(f"No {sport} games found")
        return False

    print("\nTARGET GAME")
    print("-" * 60)
    print(f"ID: {sample_game.game_id}")
    print(f"{sample_game.away_team} @ {sample_game.home_team}")

    # Test WITHOUT symmetry
    print("\n1. WITHOUT symmetry (use_symmetry=False):")
    results_no_sym = find_similar_games(db, sport, sample_game.game_id, k=10, use_symmetry=False)
    print(f"   Found {len(results_no_sym)} games")
    if results_no_sym:
        print(f"   Top similarity: {results_no_sym[0]['similarity']}%")

    # Test WITH symmetry
    print("\n2. WITH symmetry (use_symmetry=True):")
    results_with_sym = find_similar_games(db, sport, sample_game.game_id, k=10, use_symmetry=True)
    print(f"   Found {len(results_with_sym)} games")
    if results_with_sym:
        print(f"   Top similarity: {results_with_sym[0]['similarity']}%")

    # Compare results
    no_sym_ids = {g['game_id'] for g in results_no_sym}
    with_sym_ids = {g['game_id'] for g in results_with_sym}
    new_games = with_sym_ids - no_sym_ids

    print(f"\n3. Comparison:")
    print(f"   Games only found with symmetry: {len(new_games)}")

    if new_games:
        print(f"\n   New games from symmetry search:")
        for game in results_with_sym:
            if game['game_id'] in new_games:
                print(f"   - {game['away']} @ {game['home']}")
                print(f"     Similarity: {game['similarity']}%")

    return True


def test_symmetric_features(db, sport: str):
    """Test symmetric features vs flip-and-search."""
    print("\n" + "=" * 60)
    print(f"TESTING {sport} SYMMETRIC FEATURES")
    print("=" * 60)

    model = NBAGameFeatures if sport == 'NBA' else NFLGameFeatures

    # Get a sample game
    sample_game = db.query(model).first()
    if not sample_game:
        print(f"No {sport} games found")
        return False

    print("\nTARGET GAME")
    print("-" * 60)
    print(f"ID: {sample_game.game_id}")
    print(f"{sample_game.away_team} @ {sample_game.home_team}")

    # Test with flip-and-search
    print("\n1. Flip-and-search (use_symmetry=True):")
    results_flip = find_similar_games(db, sport, sample_game.game_id, k=10, use_symmetry=True, use_symmetric=False)
    print(f"   Found {len(results_flip)} games")
    if results_flip:
        print(f"   Top 3 similarities: {[g['similarity'] for g in results_flip[:3]]}")

    # Test with symmetric features
    print("\n2. Symmetric features (use_symmetric=True):")
    results_symmetric = find_similar_games(db, sport, sample_game.game_id, k=10, use_symmetric=True)
    print(f"   Found {len(results_symmetric)} games")
    if results_symmetric:
        print(f"   Top 3 similarities: {[g['similarity'] for g in results_symmetric[:3]]}")

    # Compare
    flip_ids = set(g['game_id'] for g in results_flip)
    symmetric_ids = set(g['game_id'] for g in results_symmetric)

    overlap = flip_ids & symmetric_ids
    only_flip = flip_ids - symmetric_ids
    only_symmetric = symmetric_ids - flip_ids

    print(f"\n3. Comparison:")
    print(f"   Games in both results: {len(overlap)}")
    print(f"   Only in flip-and-search: {len(only_flip)}")
    print(f"   Only in symmetric: {len(only_symmetric)}")

    if only_symmetric:
        print(f"\n   New games from symmetric features:")
        for game in results_symmetric[:5]:
            if game['game_id'] in only_symmetric:
                print(f"   - {game['away']} @ {game['home']}: {game['similarity']}%")

    return True


def main():
    """Test KNN with available sports data."""
    db = SessionLocal()

    try:
        # Check what data we have
        nba_count = db.query(NBAGameFeatures).count()
        nfl_count = db.query(NFLGameFeatures).count()

        print("=" * 60)
        print("DATABASE STATUS")
        print("=" * 60)
        print(f"NBA games: {nba_count}")
        print(f"NFL games: {nfl_count}")

        # Test each sport that has data
        success = False
        if nba_count > 0:
            success = test_sport(db, 'NBA') or success
            test_symmetry(db, 'NBA')
            test_symmetric_features(db, 'NBA')

        if nfl_count > 0:
            success = test_sport(db, 'NFL') or success
            test_symmetry(db, 'NFL')
            test_symmetric_features(db, 'NFL')

        if not success:
            print("\n✗ No games found to test")
            return

        print("=" * 60)
        print("✓ All tests completed successfully")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
