import datetime as dt
from datetime import datetime, timedelta
import asyncio
import aiohttp
import json
from collections import deque
from dataclasses import dataclass
from typing import Optional

# Global rate limiting infrastructure
_polymarket_semaphore = asyncio.Semaphore(100)  # Limit concurrent requests
_polymarket_request_times = deque()
_polymarket_lock = asyncio.Lock()
_MAX_REQUESTS_PER_SECOND = 20

# Simple cache for live markets
@dataclass
class MarketCache:
    data: list[dict]
    timestamp: datetime
    ttl_seconds: int = 300  # 5 minutes

    def is_expired(self) -> bool:
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

_market_cache: dict[str, MarketCache] = {}


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

    Note: Polymarket sometimes reverses team order in slugs. This function tries both orders.
    """
    async with _polymarket_semaphore:
        # Try normal order first (away-home), then reversed (home-away)
        team_orders = [
            (away_team, home_team, False),  # Normal order
            (home_team, away_team, True)     # Reversed order
        ]

        for first_team, second_team, is_reversed in team_orders:
            try:
                slug = f"{sport.lower()}-{first_team.lower()}-{second_team.lower()}-{date.strftime('%Y-%m-%d')}"
                market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                opening_price_url = "https://clob.polymarket.com/prices-history"

                # Get market metadata using rate-limited request
                data = await _rate_limited_get(session, market_url)

                start_date = datetime.fromisoformat(data["gameStartTime"].replace("Z", "+00:00"))
                start_ts = int(start_date.timestamp()) - 60
                end_ts = start_ts + 60

                clobIdTokens = json.loads(data["clobTokenIds"])
                market_open = int(datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")).timestamp())
                market_close = int(datetime.fromisoformat(data["closedTime"].replace("Z", "+00:00")).timestamp())
                queryString = {
                    "market": clobIdTokens[0],
                    "startTs": start_ts,
                    "endTs": end_ts
                }

                # Get price history using rate-limited request
                info = await _rate_limited_get(session, opening_price_url, params=queryString)

                # Extract prices
                price_first = info["history"][0]["p"]
                price_second = 1.0 - price_first

                # If reversed, swap the prices back to match away/home order
                if is_reversed:
                    away_price = price_second
                    home_price = price_first
                else:
                    away_price = price_first
                    home_price = price_second

                return {
                    "away_price": away_price,
                    "home_price": home_price,
                    "start_ts": start_ts,
                    "market_open_ts": market_open,
                    "market_close_ts": market_close
                }
            except Exception:
                # If this order failed and we haven't tried reversed yet, continue to next iteration
                if not is_reversed:
                    continue
                # If both orders failed, return empty dict
                return {}

        # Should not reach here, but return empty dict as fallback
        return {}


async def get_current_price(
    session: aiohttp.ClientSession,
    sport: str,
    date: dt.date,
    away_team: str,
    home_team: str
):
    """
    Get current price for a Polymarket game market.
    Returns dict with away_price, home_price, market_id, timestamp or empty dict on error.

    Note: Polymarket sometimes reverses team order in slugs. This function tries both orders.
    """
    async with _polymarket_semaphore:
        # Try normal order first (away-home), then reversed (home-away)
        team_orders = [
            (away_team, home_team, False),  # Normal order
            (home_team, away_team, True)     # Reversed order
        ]

        for first_team, second_team, is_reversed in team_orders:
            try:
                slug = f"{sport.lower()}-{first_team.lower()}-{second_team.lower()}-{date.strftime('%Y-%m-%d')}"
                market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                price_url = "https://clob.polymarket.com/prices-history"

                # Get market metadata using rate-limited request
                data = await _rate_limited_get(session, market_url)

                clobIdTokens = json.loads(data["clobTokenIds"])
                market_id = data.get("id", slug)  # Use market ID if available, otherwise slug

                # Get current price (most recent snapshot)
                now_ts = int(datetime.now().timestamp())
                start_ts = now_ts - 120  # Look back 2 minutes for latest price

                queryString = {
                    "market": clobIdTokens[0],
                    "startTs": start_ts,
                    "endTs": now_ts
                }

                # Get price history using rate-limited request
                info = await _rate_limited_get(session, price_url, params=queryString)

                if not info.get("history"):
                    # No price data available, return empty dict
                    return {}

                # Get most recent price
                price_first = info["history"][-1]["p"]  # Last price in history
                price_second = 1.0 - price_first

                # If reversed, swap the prices back to match away/home order
                if is_reversed:
                    away_price = price_second
                    home_price = price_first
                else:
                    away_price = price_first
                    home_price = price_second

                return {
                    "market_id": market_id,
                    "away_price": away_price,
                    "home_price": home_price,
                    "timestamp": now_ts
                }
            except Exception:
                # If this order failed and we haven't tried reversed yet, continue to next iteration
                if not is_reversed:
                    continue
                # If both orders failed, return empty dict
                return {}

        # Should not reach here, but return empty dict as fallback
        return {}


async def get_price_by_slug(session: aiohttp.ClientSession, slug: str) -> dict:
    """
    Get current price for a market using its slug directly.

    Args:
        session: aiohttp session
        slug: Polymarket slug (e.g., "nfl-giants-broncos-2024-11-08")

    Returns:
        Dict with away_price, home_price, timestamp or empty dict on error
    """
    try:
        market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        price_url = "https://clob.polymarket.com/prices-history"

        # Get market metadata
        async with _polymarket_semaphore:
            data = await _rate_limited_get(session, market_url)

            import json
            clobIdTokens = json.loads(data["clobTokenIds"])

            # Get current price (last 2 minutes)
            from datetime import datetime
            now_ts = int(datetime.now().timestamp())
            start_ts = now_ts - 120

            queryString = {
                "market": clobIdTokens[0],
                "startTs": start_ts,
                "endTs": now_ts
            }

            info = await _rate_limited_get(session, price_url, params=queryString)

            if not info.get("history"):
                return {}

            # Get most recent price
            price_first = info["history"][-1]["p"]
            price_second = 1.0 - price_first

            return {
                "away_price": price_first,
                "home_price": price_second,
                "timestamp": now_ts
            }

    except Exception as e:
        print(f"Error fetching price for {slug}: {e}")
        return {}


async def check_market_exists(
    session: aiohttp.ClientSession,
    sport: str,
    date: dt.date,
    away_team: str,
    home_team: str
) -> dict:
    """
    Check if a Polymarket market exists for a given game.

    Returns dict with:
        - exists (bool): True if market exists
        - market_id (str): Polymarket market ID if exists
        - polymarket_slug (str): URL slug if exists
        - game_start_ts (datetime): Game start time if exists
        - market_open_ts (datetime): Market open time if exists
        - market_close_ts (datetime): Market close time if exists

    Or returns dict with exists=False if market doesn't exist.
    """
    async with _polymarket_semaphore:
        # Try normal order first (away-home), then reversed (home-away)
        team_orders = [
            (away_team, home_team),  # Normal order
            (home_team, away_team)   # Reversed order
        ]

        for first_team, second_team in team_orders:
            try:
                slug = f"{sport.lower()}-{first_team.lower()}-{second_team.lower()}-{date.strftime('%Y-%m-%d')}"
                market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"

                # Get market metadata using rate-limited request
                data = await _rate_limited_get(session, market_url)

                # If we got here, market exists
                market_id = data.get("id", slug)
                start_date = datetime.fromisoformat(data["gameStartTime"].replace("Z", "+00:00"))
                market_open = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")) # startDate
                market_close = datetime.fromisoformat(data["closedTime"].replace("Z", "+00:00")) # endDate

                return {
                    "exists": True,
                    "market_id": market_id,
                    "polymarket_slug": slug,
                    "game_start_ts": start_date,
                    "market_open_ts": market_open,
                    "market_close_ts": market_close
                }
            except Exception:
                # If normal order failed, try reversed
                continue

        # Both orders failed, market doesn't exist
        return {"exists": False}


async def get_active_sports_markets(
    session: aiohttp.ClientSession,
    sport: str,
    limit: int = 50
) -> list[dict]:
    """
    Fetch all active sports markets for a given league from Polymarket.

    Args:
        session: aiohttp ClientSession
        sport: "nfl" or "nba" (case-insensitive)
        limit: Max results to return

    Returns:
        List of market dicts with structure:
        [{
            "event_id": str,
            "slug": str,
            "title": str,
            "game_date": datetime,
            "away_team": str,
            "home_team": str,
            "away_price": float,
            "home_price": float,
            "volume": float,
        }, ...]
    """
    # Map sport to Polymarket tag_id
    SPORT_TAG_MAP = {
        "nfl": "450",
        "nba": "745"
    }

    tag_id = SPORT_TAG_MAP.get(sport.lower())
    if not tag_id:
        print(f"Unknown sport: {sport}")
        return []

    url = "https://gamma-api.polymarket.com/events"
    params = {
        "closed": "false",
        "tag_id": tag_id,
        "limit": str(limit),
        "offset": "0",
        "order": "id",
        "ascending": "false"
    }

    try:
        # Use existing rate limiting
        data = await _rate_limited_get(session, url, params=params)

        markets = []
        for event in data:
            slug = event.get("slug", "")
            title = event.get("title", "")

            # Extract teams from slug (format: sport-away-home-date)
            parts = slug.split("-")
            if len(parts) >= 4:
                away_team = parts[1].replace("_", " ").title()
                home_team = parts[2].replace("_", " ").title()
            else:
                # Fallback: parse from title
                away_team, home_team = _parse_teams_from_title(title)

            # Get first market (main moneyline market)
            market_list = event.get("markets", [])
            if not market_list:
                continue

            market = market_list[0]
            prices_str = market.get("outcomePrices", '["0.5", "0.5"]')
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str

            # Parse game date
            start_date_str = event.get("startDate", "")
            if start_date_str:
                game_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            else:
                continue

            markets.append({
                "event_id": event.get("id"),
                "slug": slug,
                "title": title,
                "game_date": game_date,
                "away_team": away_team,
                "home_team": home_team,
                "away_price": float(prices[0]),
                "home_price": float(prices[1]),
                "volume": event.get("volume", 0),
            })

        return markets

    except Exception as e:
        print(f"Error fetching {sport} markets: {e}")
        return []


def _parse_teams_from_title(title: str) -> tuple[str, str]:
    """Parse away/home teams from title like 'Team1 vs Team2'"""
    if " vs " in title:
        parts = title.split(" vs ")
        return parts[0].strip(), parts[1].strip()
    elif " @ " in title:
        parts = title.split(" @ ")
        return parts[0].strip(), parts[1].strip()
    return ("Unknown", "Unknown")


async def get_active_sports_markets_cached(
    session: aiohttp.ClientSession,
    sport: str,
    limit: int = 50,
    force_refresh: bool = False
) -> list[dict]:
    """
    Cached version of get_active_sports_markets with 5-minute TTL.

    Args:
        session: aiohttp ClientSession
        sport: "nfl" or "nba"
        limit: Max results to return
        force_refresh: If True, bypass cache

    Returns:
        List of market dicts (same as get_active_sports_markets)
    """
    cache_key = f"{sport.lower()}_{limit}"

    # Check cache
    if not force_refresh and cache_key in _market_cache:
        cached = _market_cache[cache_key]
        if not cached.is_expired():
            return cached.data

    # Fetch fresh data
    markets = await get_active_sports_markets(session, sport, limit)

    # Update cache
    _market_cache[cache_key] = MarketCache(
        data=markets,
        timestamp=datetime.now(),
        ttl_seconds=300  # 5 minutes
    )

    return markets


async def get_price_history(
    session: aiohttp.ClientSession,
    sport: str,
    date: dt.date,
    away_team: str,
    home_team: str,
    include_game_interval: bool = False
) -> dict:
    """
    Get price history for a Polymarket game market.

    Fetches full market price history from market_open_ts to market_close_ts.
    Optionally includes filtered history from game_start_ts to market_close_ts.

    Args:
        session: aiohttp ClientSession for making requests
        sport: Sport type (e.g., "NBA", "NFL", "MLB")
        date: Game date
        away_team: Away team name (Polymarket format)
        home_team: Home team name (Polymarket format)
        include_game_interval: If True, also includes game_history (from game start to close)

    Returns:
        Dict with structure:
        {
            "full_history": [
                {"timestamp": int, "away_price": float, "home_price": float},
                ...
            ],
            "game_history": [...],  # Only if include_game_interval=True
            "market_open_ts": int,
            "market_close_ts": int,
            "game_start_ts": int
        }

        Returns empty dict {} if market doesn't exist or error occurs.

    Note: Polymarket sometimes reverses team order in slugs. This function tries both orders.
    """
    async with _polymarket_semaphore:
        # Try normal order first (away-home), then reversed (home-away)
        team_orders = [
            (away_team, home_team, False),  # Normal order
            (home_team, away_team, True)     # Reversed order
        ]

        for first_team, second_team, is_reversed in team_orders:
            try:
                slug = f"{sport.lower()}-{first_team.lower()}-{second_team.lower()}-{date.strftime('%Y-%m-%d')}"
                market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                price_history_url = "https://clob.polymarket.com/prices-history"

                # Get market metadata using rate-limited request
                data = await _rate_limited_get(session, market_url)

                # Extract timestamps
                game_start_dt = datetime.fromisoformat(data["gameStartTime"].replace("Z", "+00:00"))
                market_open_dt = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
                market_close_dt = datetime.fromisoformat(data["closedTime"].replace("Z", "+00:00"))

                game_start_ts = int(game_start_dt.timestamp())
                market_open_ts = int(market_open_dt.timestamp())
                market_close_ts = int(market_close_dt.timestamp())

                # Extract clob token for price queries
                clobIdTokens = json.loads(data["clobTokenIds"])
                market_token = clobIdTokens[0]

                # Fetch full price history (market open to close)
                queryString = {
                    "market": market_token,
                    "startTs": market_open_ts,
                    "endTs": market_close_ts
                }

                # Get price history using rate-limited request
                history_data = await _rate_limited_get(session, price_history_url, params=queryString)

                # Process full history data
                full_history = []
                for entry in history_data.get("history", []):
                    price_first = entry["p"]
                    price_second = 1.0 - price_first
                    timestamp = entry["t"]

                    # Handle price reversal if team order was reversed
                    if is_reversed:
                        away_price = price_second
                        home_price = price_first
                    else:
                        away_price = price_first
                        home_price = price_second

                    full_history.append({
                        "timestamp": timestamp,
                        "away_price": away_price,
                        "home_price": home_price
                    })

                # Build result
                result = {
                    "full_history": full_history,
                    "market_open_ts": market_open_ts,
                    "market_close_ts": market_close_ts,
                    "game_start_ts": game_start_ts
                }

                # If requested, filter for game interval (in-memory, no extra API call)
                if include_game_interval:
                    game_history = [
                        entry for entry in full_history
                        if entry["timestamp"] >= game_start_ts
                    ]
                    result["game_history"] = game_history

                return result

            except Exception:
                # If this order failed and we haven't tried reversed yet, continue
                if not is_reversed:
                    continue
                # If both orders failed, return empty dict
                return {}

        # Should not reach here, but return empty dict as fallback
        return {}