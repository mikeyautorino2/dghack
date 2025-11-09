"""
FastAPI backend for NFL betting markets application.

Provides endpoints for:
- Listing active NFL markets
- Finding similar historical matchups using KNN
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import SessionLocal, ActiveMarket, NFLGameFeatures
from .services.knn_service import find_similar_games

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
