"""
Service for batch fetching price histories from Polymarket.
"""
import asyncio
import aiohttp
from typing import List, Dict, Any
from datetime import date

from backend.services import polymarket_api


async def fetch_price_histories_batch(
    games: List[Dict[str, Any]],
    include_game_interval: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    Batch fetch price histories for multiple games from Polymarket.

    Args:
        games: List of game dicts, each containing:
            - game_id (str): Game identifier
            - sport (str): Sport type (NBA, NFL, MLB)
            - game_date (date): Date of the game
            - away_team (str): Away team name (Polymarket format)
            - home_team (str): Home team name (Polymarket format)
        include_game_interval: If True, includes game_history in addition to full_history

    Returns:
        Dict mapping game_id to price history data:
        {
            "game_id_1": {
                "full_history": [...],
                "game_history": [...],  # If include_game_interval=True
                "market_open_ts": int,
                "market_close_ts": int,
                "game_start_ts": int
            },
            "game_id_2": {...},
            ...
        }

        Games without Polymarket data will have empty dict as value.
    """
    async with aiohttp.ClientSession() as session:
        # Create tasks for fetching all price histories concurrently
        tasks = []
        for game in games:
            task = polymarket_api.get_price_history(
                session=session,
                sport=game["sport"],
                date=game["game_date"],
                away_team=game["away_team"],
                home_team=game["home_team"],
                include_game_interval=include_game_interval
            )
            tasks.append((game["game_id"], task))

        # Execute all tasks concurrently
        results = {}
        for game_id, task in tasks:
            try:
                price_data = await task
                results[game_id] = price_data
            except Exception as e:
                # If fetch fails, store empty dict for this game
                print(f"Failed to fetch price history for game {game_id}: {e}")
                results[game_id] = {}

        return results
