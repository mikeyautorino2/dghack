"""Simple KNN for finding similar games."""
from sqlalchemy.orm import Session
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import numpy as np
from app.db import NBAGameFeatures, NFLGameFeatures

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

    # Transform if using symmetric mode
    if use_symmetric:
        target_vals = _transform_symmetric_features(target_vals)

    target_scaled = scaler.transform([target_vals])

    # Query cached model (fast!)
    distances, indices = knn_model.kneighbors(target_scaled)

    # If using symmetric features, no need for flip-and-search (symmetry is built-in)
    if use_symmetric:
        # Simple single search
        results = []
        max_dist = distances[0].max() if distances[0].max() > 0 else 1

        for i, idx in enumerate(indices[0][:k]):
            game = all_games[idx]
            similarity = 100 * (1 - distances[0][i] / max_dist)
            results.append({
                'game_id': game.game_id,
                'date': game.game_date,
                'home': game.home_team,
                'away': game.away_team,
                'similarity': round(similarity, 1)
            })
        return results

    # Otherwise, use flip-and-search approach
    results_dict = {}
    max_dist = distances[0].max() if distances[0].max() > 0 else 1

    for i, idx in enumerate(indices[0]):
        game = all_games[idx]
        similarity = 100 * (1 - distances[0][i] / max_dist)
        if game.game_id not in results_dict:
            results_dict[game.game_id] = {
                'game_id': game.game_id,
                'date': game.game_date,
                'home': game.home_team,
                'away': game.away_team,
                'similarity': round(similarity, 1)
            }

    # If symmetry enabled, also search with flipped features
    if use_symmetry:
        flipped_vals = _flip_features(target_vals, features)
        flipped_scaled = scaler.transform([flipped_vals])

        distances_flip, indices_flip = knn_model.kneighbors(flipped_scaled)
        max_dist_flip = distances_flip[0].max() if distances_flip[0].max() > 0 else 1

        for i, idx in enumerate(indices_flip[0]):
            game = all_games[idx]
            similarity = 100 * (1 - distances_flip[0][i] / max_dist_flip)
            if game.game_id not in results_dict:
                results_dict[game.game_id] = {
                    'game_id': game.game_id,
                    'date': game.game_date,
                    'home': game.home_team,
                    'away': game.away_team,
                    'similarity': round(similarity, 1)
                }
            else:
                # Keep higher similarity score
                results_dict[game.game_id]['similarity'] = round(
                    max(results_dict[game.game_id]['similarity'], similarity), 1
                )

    # Sort by similarity and return top k
    results = sorted(results_dict.values(), key=lambda x: x['similarity'], reverse=True)[:k]
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
