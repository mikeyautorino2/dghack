import aiohttp
import asyncio
import datetime as dt
from typing import Optional, Dict
from collections import deque

# Global rate limiter state
_kalshi_semaphore = asyncio.Semaphore(100)  # Limit concurrent games
_kalshi_request_times = deque()
_kalshi_lock = asyncio.Lock()
_MAX_REQUESTS_PER_SECOND = 20


async def _rate_limited_get(session: aiohttp.ClientSession, url: str, timeout: int = 20):
    """Make a rate-limited GET request to Kalshi API (20 req/sec limit)."""
    global _kalshi_request_times
    
    while True:  # Retry loop for rate limiting
        async with _kalshi_lock:
            now = asyncio.get_event_loop().time()
            
            # Remove requests older than 1 second
            while _kalshi_request_times and now - _kalshi_request_times[0] >= 1.0:
                _kalshi_request_times.popleft()
            
            # If we've made MAX requests in the last second, wait
            if len(_kalshi_request_times) >= _MAX_REQUESTS_PER_SECOND:
                sleep_time = 1.1 - (now - _kalshi_request_times[0])  # 100ms buffer
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    continue  # Re-check after sleeping
            
            # Record this request BEFORE making it
            _kalshi_request_times.append(now)
        
        # Make the actual request outside the lock
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 429:
                    print(f"Rate limited (429) for {url.split('/')[-1]}, retrying...")
                    await asyncio.sleep(1.0)
                    continue  # Retry the request
                return response.status, await response.json() if response.status == 200 else None
        except asyncio.TimeoutError:
            print(f"Timeout for {url.split('/')[-1]}")
            return None, None
        except Exception as e:
            print(f"Request failed for {url.split('/')[-1]}: {e}")
            return None, None


async def get_market_data(session: aiohttp.ClientSession,
                          series_ticker: str, 
                          date: dt.date, 
                          away_team: str, 
                          home_team: str) -> Dict:
    """Fetch Kalshi market data for a game.
    
    Args:
        session: aiohttp session
        series_ticker: Series ticker (e.g., "KXMLBGAME")
        date: Game date
        away_team: Away team abbreviation
        home_team: Home team abbreviation
    """
    
    async with _kalshi_semaphore:
        base_event_ticker = f"{series_ticker}-{date.strftime('%y%b%d').upper()}{away_team}{home_team}"
        event_ticker = base_event_ticker

        try:
            # Try base event ticker first
            url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?related_event_ticker={event_ticker}&limit=10"
            status, data = await _rate_limited_get(session, url)
            
            if status != 200 or not data:
                return {}
            
            # If milestones is empty, try with G1 suffix
            if not data.get("milestones"):
                return {}
            
                # event_ticker = f"{base_event_ticker}G1"
                # url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?related_event_ticker={event_ticker}&limit=10"
                # status, data = await _rate_limited_get(session, url)
                
                # if status != 200 or not data:
                #     return {}
                
                # # If still empty, try with G2 suffix
                # if not data.get("milestones"):
                #     event_ticker = f"{base_event_ticker}G2"
                #     url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?related_event_ticker={event_ticker}&limit=10"
                #     status, data = await _rate_limited_get(session, url)
                    
                #     if status != 200 or not data or not data.get("milestones"):
                #         return {}
            
            start_time_str = data["milestones"][0]["start_date"]
            start_dt = dt.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        
            start_ts = int(start_dt.timestamp()) - 60
            
            # Use the resolved event_ticker for subsequent API calls
            candlesticks_url = f"https://api.elections.kalshi.com/trade-api/v2/series/{series_ticker}/events/{event_ticker}/candlesticks?start_ts={start_ts}&end_ts={start_ts}&period_interval=1"
            candlesticks_status, candlesticks_data = await _rate_limited_get(session, candlesticks_url)
            
            if candlesticks_status != 200 or not candlesticks_data:
                return {}
            
            event_url = f"https://api.elections.kalshi.com/trade-api/v2/events/{event_ticker}"
            event_status, event_data = await _rate_limited_get(session, event_url)
            
            if event_status != 200 or not event_data:
                return {}

            # Process candlesticks data
            market_tickers = candlesticks_data.get("market_tickers", [])
            if not market_tickers:
                return {}
                
            t1 = market_tickers[0].split('-')[-1]
            away_team_idx = 0 if t1 == away_team else 1
            home_team_idx = 1 if t1 == away_team else 0
            
            def get_mid_price(candle):
                try:
                    bid = candle["yes_bid"]["close"]
                    ask = candle["yes_ask"]["close"]
                    if bid is not None and ask is not None:
                        return (bid + ask) / 2
                except (KeyError, TypeError):
                    pass
                return None

            market_candlesticks = candlesticks_data.get("market_candlesticks", [])
            if len(market_candlesticks) <= max(away_team_idx, home_team_idx):
                return {}
            if not market_candlesticks[away_team_idx] or not market_candlesticks[home_team_idx]:
                return {}
                
            away_candle = market_candlesticks[away_team_idx][0]
            home_candle = market_candlesticks[home_team_idx][0]
            
            away_price = get_mid_price(away_candle)
            home_price = get_mid_price(home_candle)

            # Process event data
            markets = event_data.get("markets", [])
            if not markets:
                return {}
                
            open_time_str = markets[0]["open_time"]
            open_dt = dt.datetime.fromisoformat(open_time_str.replace("Z", "+00:00"))
            open_ts = int(open_dt.timestamp())

            close_time_str = markets[0]["close_time"]
            close_dt = dt.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
            close_ts = int(close_dt.timestamp())

            result = {
                "away_price": away_price,
                "home_price": home_price,
                "start_ts": start_ts,
                "market_open_ts": open_ts,
                "market_close_ts": close_ts
            }
            return result
        
        except Exception as e:
            print(f"Error fetching market data for {event_ticker}: {e}")
            return {}