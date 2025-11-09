"""
FastAPI backend for NFL and NBA betting markets application.

Provides endpoints for:
- Listing active markets
- Finding similar historical matchups using KNN
- Getting price history for similar games
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiohttp
import asyncio
from .db import SessionLocal, ActiveMarket, NFLGameFeatures, NBAGameFeatures
from .services.knn_service import find_similar_games
from .services.price_history_service import fetch_price_histories_batch
from .team_mappings import get_polymarket_abbrev
from backend.services import polymarket_api

app = FastAPI(title="Sports Betting Markets API")

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
    return {"status": "ok", "message": "Sports Betting Markets API"}


@app.get("/api/markets")
async def get_active_markets(sport: str = "NBA"):
    """
    Get recent historical games with Polymarket prices that can be analyzed.

    Query param: ?sport=NFL or ?sport=NBA (default: NBA)

    Returns list of recent games that have:
    - Historical team statistics (already played)
    - Polymarket price data
    - Can be analyzed via KNN for similar matchups
    """
    db = SessionLocal()
    try:
        # Get the appropriate model based on sport
        model = NBAGameFeatures if sport.upper() == 'NBA' else NFLGameFeatures

        # Query recent games with Polymarket data
        # Filter for games that have price data and order by most recent
        recent_games = db.query(model).filter(
            model.polymarket_home_price.isnot(None),
            model.polymarket_away_price.isnot(None)
        ).order_by(model.game_date.desc()).limit(50).all()

        if not recent_games:
            return []

        # Build results in format frontend expects
        results = []
        for game in recent_games:
            results.append({
                'game_id': game.game_id,
                'sport': game.sport,
                'away_team': game.away_team,
                'home_team': game.home_team,
                'game_date': str(game.game_date),
                'game_start_ts': game.polymarket_start_ts if game.polymarket_start_ts else 0,
                'polymarket_away_price': game.polymarket_away_price,
                'polymarket_home_price': game.polymarket_home_price,
                'polymarket_slug': ''  # Not needed for historical games
            })

        return results

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


@app.get("/api/games/{sport}/{game_id}/live-market")
async def get_live_market(sport: str, game_id: str):
    """
    Get current live market price for the target game.

    Checks if an active Polymarket market exists for this game and returns
    the current price. Used for real-time polling on game detail page.

    Args:
        sport: Sport type (NBA or NFL)
        game_id: Game ID from database

    Returns:
        {
            "exists": bool,
            "market_id": str | null,
            "polymarket_slug": str | null,
            "away_team": str,
            "home_team": str,
            "away_price": float | null,
            "home_price": float | null,
            "timestamp": int | null
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

        # Get target game from database or ActiveMarket
        target_game = db.query(model).filter_by(game_id=game_id).first()

        if not target_game:
            # Check if it's an upcoming game in ActiveMarket
            active_market = db.query(ActiveMarket).filter_by(market_id=game_id).first()

            if not active_market:
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

            # Use active market's info
            away_team_str = str(active_market.away_team)
            home_team_str = str(active_market.home_team)
            game_date_val = active_market.game_date
        else:
            # Use historical game's info
            away_team_str = str(target_game.away_team)
            home_team_str = str(target_game.home_team)
            game_date_val = target_game.game_date

        # Convert team names to Polymarket abbreviations
        try:
            away_abbrev = get_polymarket_abbrev(away_team_str, sport_upper)
            home_abbrev = get_polymarket_abbrev(home_team_str, sport_upper)
        except ValueError as e:
            # Team name not in mapping - return market doesn't exist
            return {
                "exists": False,
                "market_id": None,
                "polymarket_slug": None,
                "away_team": target_game.away_team,
                "home_team": target_game.home_team,
                "away_price": None,
                "home_price": None,
                "timestamp": None
            }

        # Check if market exists on Polymarket
        async with aiohttp.ClientSession() as session:
            market_info = await polymarket_api.check_market_exists(
                session=session,
                sport=sport_upper,
                date=game_date_val,
                away_team=away_abbrev,
                home_team=home_abbrev
            )

            if not market_info or not market_info.get('exists'):
                return {
                    "exists": False,
                    "market_id": None,
                    "polymarket_slug": None,
                    "away_team": away_team_str,
                    "home_team": home_team_str,
                    "away_price": None,
                    "home_price": None,
                    "timestamp": None
                }

            # Market exists - fetch current price
            current_price = await polymarket_api.get_current_price(
                session=session,
                sport=sport_upper,
                date=game_date_val,
                away_team=away_abbrev,
                home_team=home_abbrev
            )

            return {
                "exists": True,
                "market_id": current_price.get('market_id'),
                "polymarket_slug": market_info.get('slug'),
                "away_team": away_team_str,
                "home_team": home_team_str,
                "away_price": current_price.get('away_price'),
                "home_price": current_price.get('home_price'),
                "timestamp": current_price.get('timestamp')
            }

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

        # If not found in historical tables, check if it's an upcoming game in ActiveMarket
        if not target_game:
            active_market = db.query(ActiveMarket).filter_by(market_id=game_id).first()

            if active_market:
                # This is an upcoming game - get latest team stats and run KNN
                away_team_str = str(active_market.away_team)
                home_team_str = str(active_market.home_team)

                # Get most recent games for each team to extract current season stats
                # For away team: get their most recent game as away team
                away_latest = db.query(model).filter(
                    model.away_team == away_team_str
                ).order_by(model.game_date.desc()).first()

                # For home team: get their most recent game as home team
                home_latest = db.query(model).filter(
                    model.home_team == home_team_str
                ).order_by(model.game_date.desc()).first()

                if not away_latest or not home_latest:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No historical stats found for {away_team_str} or {home_team_str}"
                    )

                # Create synthetic upcoming game using latest stats
                # Use a special game_id that we'll recognize later
                synthetic_game_id = f"upcoming_{active_market.market_id}"

                # Find similar games using the latest team stats
                # We'll pass the synthetic game_id and the KNN service will handle it
                similar_games = find_similar_games(
                    db, sport_upper, synthetic_game_id, k=k,
                    away_stats_game=away_latest, home_stats_game=home_latest
                )

                # Return with upcoming game as target
                target_game_info = {
                    "game_id": str(active_market.market_id),
                    "sport": str(active_market.sport),
                    "date": str(active_market.game_date),
                    "home_team": home_team_str,
                    "away_team": away_team_str
                }

                # If no similar games, return early
                if not similar_games:
                    return {
                        "target_game": target_game_info,
                        "similar_games": []
                    }

                # Continue with price history fetching for similar games
                # (rest of the code will handle this)

            else:
                # Not in historical tables and not in ActiveMarket
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        else:
            # Found in historical tables - use normal KNN
            similar_games = find_similar_games(db, sport_upper, game_id, k=k)

            target_game_info = {
                "game_id": str(target_game.game_id),
                "sport": str(target_game.sport),
                "date": str(target_game.game_date),
                "home_team": str(target_game.home_team),
                "away_team": str(target_game.away_team)
            }

        if not similar_games:
            # No similar games found, return just target game info
            return {
                "target_game": target_game_info,
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
            "target_game": target_game_info,
            "similar_games": results
        }

    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
