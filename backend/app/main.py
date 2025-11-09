"""
FastAPI backend for NFL and NBA betting markets application.

Provides endpoints for:
- Listing active markets
- Finding similar historical matchups using KNN
- Getting price history for similar games
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .db import SessionLocal, ActiveMarket, NFLGameFeatures, NBAGameFeatures
from .services.knn_service import find_similar_games
from .services.price_history_service import fetch_price_histories_batch
from .team_mappings import get_polymarket_abbrev

app = FastAPI(title="NFL Betting Markets API")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "NFL Betting Markets API"}


@app.get("/api/markets")
def get_active_markets():
    """
    Get list of active NFL betting markets.

    Returns markets with status='open' sorted by game start time.
    """
    db = SessionLocal()
    try:
        markets = db.query(ActiveMarket).filter_by(
            sport='NFL',
            market_status='open'
        ).order_by(ActiveMarket.game_start_ts).all()

        return [{
            'market_id': m.market_id,
            'away_team': m.away_team,
            'home_team': m.home_team,
            'game_date': str(m.game_date),
            'game_start_ts': m.game_start_ts,
            'polymarket_slug': m.polymarket_slug
        } for m in markets]
    finally:
        db.close()


@app.get("/api/markets/{market_id}/similar")
def get_similar_matchups(market_id: str, k: int = 5):
    """
    Get similar historical matchups for a market using KNN.

    Args:
        market_id: Polymarket market ID
        k: Number of similar games to return (default: 5)

    Returns:
        List of similar games with similarity scores
    """
    db = SessionLocal()
    try:
        # Get the active market
        market = db.query(ActiveMarket).filter_by(market_id=market_id).first()
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")

        # Find the corresponding game_id from NFLGameFeatures
        # Match by teams and date
        game = db.query(NFLGameFeatures).filter_by(
            game_date=market.game_date,
            away_team=market.away_team,
            home_team=market.home_team
        ).first()

        if not game:
            # No historical stats yet for this upcoming game
            return []

        # Use KNN service to find similar games
        similar = find_similar_games(db, 'NFL', game.game_id, k=k)
        return similar

    finally:
        db.close()


@app.get("/api/games/{sport}/{game_id}/analysis")
async def get_game_analysis(sport: str, game_id: str, k: int = 5):
    """
    Get similar historical games with price history for analysis.

    For a given game, returns N most similar historical games along with
    their Polymarket price histories for candlestick visualization.

    Args:
        sport: Sport type (NBA or NFL)
        game_id: Game ID from database
        k: Number of similar games to return (default: 5)

    Returns:
        {
            "target_game": {
                "game_id": str,
                "sport": str,
                "date": str,
                "home_team": str,
                "away_team": str
            },
            "similar_games": [
                {
                    "game_id": str,
                    "date": str,
                    "home_team": str,
                    "away_team": str,
                    "similarity": float,
                    "mapping": str,
                    "current_home_corresponds_to": str,
                    "current_away_corresponds_to": str,
                    "price_history": [
                        {"timestamp": int, "away_price": float, "home_price": float},
                        ...
                    ],
                    "market_metadata": {
                        "market_open_ts": int,
                        "market_close_ts": int,
                        "game_start_ts": int
                    }
                }
            ]
        }
    """
    db = SessionLocal()
    try:
        # Validate sport
        sport_upper = sport.upper()
        if sport_upper not in ['NBA', 'NFL']:
            raise HTTPException(status_code=400, detail="Sport must be NBA or NFL")

        # Get the appropriate model
        model = NBAGameFeatures if sport_upper == 'NBA' else NFLGameFeatures

        # Get target game from database
        target_game = db.query(model).filter_by(game_id=game_id).first()
        if not target_game:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # Find similar games using KNN
        similar_games = find_similar_games(db, sport_upper, game_id, k=k)

        if not similar_games:
            # No similar games found, return just target game info
            return {
                "target_game": {
                    "game_id": target_game.game_id,
                    "sport": target_game.sport,
                    "date": str(target_game.game_date),
                    "home_team": target_game.home_team,
                    "away_team": target_game.away_team
                },
                "similar_games": []
            }

        # Prepare games for price history fetching
        games_for_fetch = []
        for similar_game in similar_games:
            # Get full game object from database for date info
            game_obj = db.query(model).filter_by(game_id=similar_game['game_id']).first()
            if game_obj:
                try:
                    away_abbrev = get_polymarket_abbrev(similar_game['away'], sport_upper)
                    home_abbrev = get_polymarket_abbrev(similar_game['home'], sport_upper)
                    games_for_fetch.append({
                        "game_id": similar_game['game_id'],
                        "sport": sport_upper,
                        "game_date": game_obj.game_date,
                        "away_team": away_abbrev,
                        "home_team": home_abbrev
                    })
                except ValueError as e:
                    # Log warning but continue with other games
                    print(f"Warning: Could not convert team names for game {similar_game['game_id']}: {e}")

        # Batch fetch price histories
        price_histories = await fetch_price_histories_batch(
            games=games_for_fetch,
            include_game_interval=False  # Only need full history for now
        )

        # Combine similar games with their price histories
        results = []
        for similar_game in similar_games:
            game_id_key = similar_game['game_id']
            price_data = price_histories.get(game_id_key, {})

            result_entry = {
                "game_id": similar_game['game_id'],
                "date": str(similar_game['date']),
                "home_team": similar_game['home'],
                "away_team": similar_game['away'],
                "similarity": similar_game['similarity'],
                "mapping": similar_game['mapping'],
                "current_home_corresponds_to": similar_game['current_home_corresponds_to'],
                "current_away_corresponds_to": similar_game['current_away_corresponds_to'],
                "price_history": price_data.get('full_history', []),
                "market_metadata": {
                    "market_open_ts": price_data.get('market_open_ts'),
                    "market_close_ts": price_data.get('market_close_ts'),
                    "game_start_ts": price_data.get('game_start_ts')
                } if price_data else None
            }
            results.append(result_entry)

        return {
            "target_game": {
                "game_id": target_game.game_id,
                "sport": target_game.sport,
                "date": str(target_game.game_date),
                "home_team": target_game.home_team,
                "away_team": target_game.away_team
            },
            "similar_games": results
        }

    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
