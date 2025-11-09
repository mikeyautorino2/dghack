"""Simple KNN for finding similar games."""
from sqlalchemy.orm import Session
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import numpy as np
from ..db import NBAGameFeatures, NFLGameFeatures

# Feature definitions per sport
FEATURES = {
    'NBA': ['home_avg_pts', 'away_avg_pts', 'home_fg_pct', 'away_fg_pct',
            'home_avg_reb', 'away_avg_reb', 'home_avg_ast', 'away_avg_ast'],
    'NFL': ['home_yardsPerPlay', 'away_yardsPerPlay',
            'home_thirdDownEff', 'away_thirdDownEff',
            'home_firstDowns', 'away_firstDowns']
}

MODELS = {
    'NBA': NBAGameFeatures,
    'NFL': NFLGameFeatures
}

# Cache for fitted models: sport -> (scaler, knn, games, features)
_cache = {}
_cache_symmetric = {}


def _transform_symmetric_features(vals):
    """Transform [home_X, away_X, ...] to [max_X, min_X, ...]."""
    result = []
    for i in range(0, len(vals), 2):
        result.append(max(vals[i], vals[i+1]))
        result.append(min(vals[i], vals[i+1]))
    return result


def _fit_model(db: Session, sport: str, use_symmetric: bool = False):
    """Fit KNN model and return cached components."""
    print(f"Fitting {sport} model...")

    model = MODELS[sport]
    features = FEATURES[sport]

    # Load all games
    all_games = db.query(model).filter(
        getattr(model, features[0]).isnot(None)
    ).all()

    if len(all_games) == 0:
        return None

    # Extract features
    X = np.array([[getattr(g, f) if getattr(g, f) is not None else 0
                   for f in features] for g in all_games])

    # Transform to symmetric if requested
    if use_symmetric:
        X = np.array([_transform_symmetric_features(row) for row in X])

    # Fit scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit KNN
    knn_model = NearestNeighbors(n_neighbors=20, algorithm='ball_tree')
    knn_model.fit(X_scaled)

    print(f"Cached {len(all_games)} {sport} games")
    return (scaler, knn_model, all_games, features)


def _flip_features(feature_vals, features):
    """Flip home/away feature values for symmetry search."""
    flipped = []
    for i, feat in enumerate(features):
        if feat.startswith('home_'):
            # Find corresponding away feature
            away_feat = feat.replace('home_', 'away_')
            away_idx = features.index(away_feat)
            flipped.append(feature_vals[away_idx])
        elif feat.startswith('away_'):
            # Find corresponding home feature
            home_feat = feat.replace('away_', 'home_')
            home_idx = features.index(home_feat)
            flipped.append(feature_vals[home_idx])
        else:
            flipped.append(feature_vals[i])
    return flipped


def _determine_mapping(target_vals, similar_vals, features):
    """
    Determine if home/away mapping is direct or flipped.

    Compares distances to determine which mapping makes more sense:
    - Direct: target home ≈ similar home, target away ≈ similar away
    - Flipped: target home ≈ similar away, target away ≈ similar home

    Args:
        target_vals: Feature values for target game [home_X, away_X, ...]
        similar_vals: Feature values for similar game [home_Y, away_Y, ...]
        features: Feature names ['home_X', 'away_X', ...]

    Returns:
        dict with mapping info
    """
    # Calculate direct mapping distance
    direct_dist = sum((target_vals[i] - similar_vals[i]) ** 2
                      for i in range(len(features))) ** 0.5

    # Calculate flipped mapping distance
    flipped_dist = 0
    for i, feat in enumerate(features):
        if feat.startswith('home_'):
            away_feat = feat.replace('home_', 'away_')
            away_idx = features.index(away_feat)
            flipped_dist += (target_vals[i] - similar_vals[away_idx]) ** 2
        elif feat.startswith('away_'):
            home_feat = feat.replace('away_', 'home_')
            home_idx = features.index(home_feat)
            flipped_dist += (target_vals[i] - similar_vals[home_idx]) ** 2
    flipped_dist = flipped_dist ** 0.5

    # Choose mapping with smaller distance
    if direct_dist <= flipped_dist:
        return {
            'type': 'direct',
            'current_home_corresponds_to': 'home',
            'current_away_corresponds_to': 'away'
        }
    else:
        return {
            'type': 'flipped',
            'current_home_corresponds_to': 'away',
            'current_away_corresponds_to': 'home'
        }


def find_similar_games(db: Session, sport: str, game_id: str, k: int = 5, use_symmetry: bool = False, use_symmetric: bool = True):
    """
    Find K similar games for any sport (cached).

    Args:
        db: Database session
        sport: 'NBA' or 'NFL'
        game_id: Target game ID to find similar games for
        k: Number of similar games to return
        use_symmetry: If True, also search with flipped home/away features (ignored if use_symmetric=True)
        use_symmetric: If True (default), use symmetric feature transformation (max/min pairs)
                       This captures strength differentials which correlate with betting market probabilities

    Returns:
        List of dicts with game info and similarity scores
    """

    # Choose cache based on mode
    cache = _cache_symmetric if use_symmetric else _cache

    # Use cache if available
    if sport not in cache:
        fitted = _fit_model(db, sport, use_symmetric=use_symmetric)
        if not fitted:
            return []
        cache[sport] = fitted

    scaler, knn_model, all_games, features = cache[sport]

    # Get target game
    model = MODELS[sport]
    target = db.query(model).filter_by(game_id=game_id).first()
    if not target:
        return []

    # Extract target features
    target_vals = [getattr(target, f) for f in features]

    # Store original target features for mapping determination
    target_vals_original = target_vals.copy()

    # Transform if using symmetric mode
    if use_symmetric:
        target_vals = _transform_symmetric_features(target_vals)

    target_scaled = scaler.transform([target_vals])

    # Query cached model (fast!)
    # Request k+1 to account for query game potentially being in results
    distances, indices = knn_model.kneighbors(target_scaled, n_neighbors=k+1)

    # If using symmetric features, no need for flip-and-search (symmetry is built-in)
    if use_symmetric:
        # First pass: collect valid games (excluding query game)
        valid_games = []
        for i, idx in enumerate(indices[0]):
            game = all_games[idx]
            # Skip the query game itself
            if game.game_id == game_id:
                continue
            valid_games.append((game, distances[0][i]))
            # Stop once we have k results
            if len(valid_games) >= k:
                break

        # Handle edge case
        if not valid_games:
            return []

        # Use absolute normalization with fixed reference scale
        # In standardized euclidean space, typical distances range from 0 to ~2-3
        # Map: distance 0 → 100% similarity, distance 2.0 → 0% similarity
        max_reference = 2.0

        # Build results with absolute normalization and mapping info
        results = []
        for game, dist in valid_games:
            # Get similar game features for mapping determination
            similar_vals = [getattr(game, f) for f in features]

            # Determine team mapping
            mapping = _determine_mapping(target_vals_original, similar_vals, features)

            similarity = 100 * max(0, (1 - dist / max_reference))
            results.append({
                'game_id': game.game_id,
                'date': game.game_date,
                'home': game.home_team,
                'away': game.away_team,
                'similarity': round(similarity, 1),
                'mapping': mapping['type'],
                'current_home_corresponds_to': mapping['current_home_corresponds_to'],
                'current_away_corresponds_to': mapping['current_away_corresponds_to']
            })
        return results

    # Otherwise, use flip-and-search approach
    # Collect valid games from original search
    valid_games_dict = {}  # game_id -> (game, distance)

    for i, idx in enumerate(indices[0]):
        game = all_games[idx]
        # Skip the query game itself
        if game.game_id == game_id:
            continue
        if game.game_id not in valid_games_dict:
            valid_games_dict[game.game_id] = (game, distances[0][i])

    # If symmetry enabled, also search with flipped features
    if use_symmetry:
        flipped_vals = _flip_features(target_vals, features)
        flipped_scaled = scaler.transform([flipped_vals])

        distances_flip, indices_flip = knn_model.kneighbors(flipped_scaled, n_neighbors=k+1)

        # Collect valid games from flipped search
        for i, idx in enumerate(indices_flip[0]):
            game = all_games[idx]
            # Skip the query game itself
            if game.game_id == game_id:
                continue
            # Keep the game with smaller distance (better match)
            if game.game_id not in valid_games_dict:
                valid_games_dict[game.game_id] = (game, distances_flip[0][i])
            else:
                existing_dist = valid_games_dict[game.game_id][1]
                if distances_flip[0][i] < existing_dist:
                    valid_games_dict[game.game_id] = (game, distances_flip[0][i])

    # Handle edge case
    if not valid_games_dict:
        return []

    # Use absolute normalization with fixed reference scale
    max_reference = 2.0

    # Build results with absolute normalization and mapping info
    results = []
    for game, dist in valid_games_dict.values():
        # Get similar game features for mapping determination
        similar_vals = [getattr(game, f) for f in features]

        # Determine team mapping
        mapping = _determine_mapping(target_vals_original, similar_vals, features)

        similarity = 100 * max(0, (1 - dist / max_reference))
        results.append({
            'game_id': game.game_id,
            'date': game.game_date,
            'home': game.home_team,
            'away': game.away_team,
            'similarity': round(similarity, 1),
            'mapping': mapping['type'],
            'current_home_corresponds_to': mapping['current_home_corresponds_to'],
            'current_away_corresponds_to': mapping['current_away_corresponds_to']
        })

    # Sort by similarity and return top k
    results = sorted(results, key=lambda x: x['similarity'], reverse=True)[:k]
    return results


def clear_cache():
    """Clear cache when new data added."""
    global _cache, _cache_symmetric
    _cache = {}
    _cache_symmetric = {}
    print("Cache cleared")


# Keep backwards compatible function for NBA
def find_similar_nba_games(db: Session, game_id: str, k: int = 5):
    """Backwards compatible NBA-only function (uses symmetric features by default)."""
    return find_similar_games(db, 'NBA', game_id, k)  # Inherits use_symmetric=True default
