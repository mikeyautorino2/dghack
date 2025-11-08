import datetime as dt
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import asyncio
import aiohttp
import json
from collections import deque

# Global rate limiting infrastructure
_polymarket_semaphore = asyncio.Semaphore(100)  # Limit concurrent requests
_polymarket_request_times = deque()
_polymarket_lock = asyncio.Lock()
_MAX_REQUESTS_PER_SECOND = 20


async def _rate_limited_get(session: aiohttp.ClientSession, url: str, **kwargs):
    """
    Make a rate-limited GET request to prevent hitting API limits.
    Enforces max 20 requests per second with retry logic for 429 responses.
    """
    while True:
        async with _polymarket_lock:
            now = asyncio.get_event_loop().time()

            # Remove requests older than 1 second
            while _polymarket_request_times and _polymarket_request_times[0] < now - 1.0:
                _polymarket_request_times.popleft()

            # Check if we need to wait
            if len(_polymarket_request_times) >= _MAX_REQUESTS_PER_SECOND:
                oldest = _polymarket_request_times[0]
                sleep_time = (oldest + 1.0 - now) + 0.1  # 100ms buffer
                await asyncio.sleep(sleep_time)
                continue

            # Record this request
            _polymarket_request_times.append(now)

        # Make the request outside the lock for better throughput
        async with session.get(url, **kwargs) as response:
            if response.status == 429:
                await asyncio.sleep(1.0)
                continue
            response.raise_for_status()
            return await response.json()


"""
Todo:
1. write function that gets opening price -> we define opening price as the prices right before a 
game starts ---> START TIME - 60 seconds (UTC SO WE CAN USE SECONDS)

    - first get the clobTokenID and start time 
    - use the /prices-history endpoint to get the price -> later on we will write this price to 
    the DB where a column could be opening_price (for that specific marketID)

2. Graphs should show from when market became available, but we should grey out less significant
information (ie the most import part is right beforre the game start to end)
3. Also store time game started AND time market openend to the DB (this will be consistent with our graph)

"""
async def get_opening_price(
    session: aiohttp.ClientSession,
    sport: str,
    date: dt.date,
    away_team: str,
    home_team: str
):
    """
    Get opening price for a Polymarket game.
    Opening price is defined as price 60 seconds before game start.
    Returns dict with away_price, home_price, start_ts, market_open_ts or empty dict on error.
    """
    async with _polymarket_semaphore:
        try:
            slug = f"{sport.lower()}-{away_team.lower()}-{home_team.lower()}-{date.strftime('%Y-%m-%d')}"
            market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
            opening_price_url = "https://clob.polymarket.com/prices-history"

            # Get market metadata using rate-limited request
            data = await _rate_limited_get(session, market_url)

            start_date = datetime.fromisoformat(data["gameStartTime"].replace("Z", "+00:00"))
            start_ts = int(start_date.timestamp()) - 60
            end_ts = start_ts + 60

            clobIdTokens = json.loads(data["clobTokenIds"])
            market_open = int(datetime.fromisoformat(data["startDate"].replace("Z", "+00:00")).timestamp())

            queryString = {
                "market": clobIdTokens[0],
                "startTs": start_ts,
                "endTs": end_ts
            }

            # Get price history using rate-limited request
            info = await _rate_limited_get(session, opening_price_url, params=queryString)

            away = info["history"][0]["p"]
            home = 1.0 - away

            return {
                "away_price": away,
                "home_price": home,
                "start_ts": start_ts,
                "market_open_ts": market_open
            }
        except Exception:
            # Return empty dict on error (consistent with kalshi_api pattern)
            return {}
