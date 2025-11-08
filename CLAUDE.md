# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a sports betting analytics project that fetches historical game data and betting market prices from multiple sports (MLB, NBA) and prediction markets (Kalshi, Polymarket). The project aggregates cumulative team statistics with market pricing data to enable arbitrage detection and analytics.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### Running Service Modules
```bash
# Test baseball data fetching (MLB)
python backend/services/baseball_api.py

# Test basketball data fetching (NBA)
python backend/services/basketball_api.py

# Test Kalshi market data
python backend/services/kalshi_api.py

# Test Polymarket data
python backend/services/polymarket_api.py
```

## Architecture

### Service Layer (`backend/services/`)

The project uses a **service-oriented architecture** where each service module handles data fetching from a specific source:

#### `baseball_api.py`
- Fetches MLB game schedules and team statistics from `statsapi.mlb.com`
- Integrates with Kalshi market data for betting prices
- Main entry point: `get_historical_data_sync(start_date, end_date, fetch_market_data=True)`
- Returns DataFrame with columns: game metadata, hitting/pitching stats (prefixed with `away_` or `home_`), and Kalshi pricing
- Uses async/await with rate limiting via semaphores (max 10 concurrent requests)
- Filters out non-regular season games, cancelled games, and doubleheaders
- **Key detail**: Only processes games from May 1st onwards (line 69)

#### `basketball_api.py`
- Fetches NBA team statistics using the `nba_api` library
- Integrates with Polymarket for betting prices
- Main entry point: `get_matchups_cumulative_stats_between(start_date, end_date)`
- Returns DataFrame with cumulative team stats (AVG_PTS, AVG_REB, FG_PCT, etc.) prefixed with `HOME_` or `AWAY_`
- Also includes Polymarket prices: `away_team_price`, `home_team_price`, `start_ts`, `market_open_ts`
- **Rate limiting**: 0.6 seconds between API calls (line 13)
- **Key detail**: Fetches cumulative stats up to (but not including) the game date

#### `kalshi_api.py`
- Fetches betting market data from Kalshi API (`api.elections.kalshi.com`)
- Main function: `get_market_data(session, series_ticker, date, away_team, home_team)`
- Returns dict with: `away_price`, `home_price`, `start_ts`, `market_open_ts`, `market_close_ts`
- **Critical rate limiting**: 20 requests/second max with retry logic for 429 responses
- Uses global deque-based rate limiter with asyncio locks
- Fetches opening prices as mid-price between bid/ask 60 seconds before game start
- **Note**: Commented-out code for handling doubleheader games (G1, G2 suffixes)

#### `polymarket_api.py`
- Fetches betting market data from Polymarket (gamma-api.polymarket.com and clob.polymarket.com)
- Main function: `get_opening_price(session, sport, date, away_team, home_team)`
- Constructs market slug: `{sport}-{away_team}-{home_team}-{date}` (all lowercase)
- Returns dict with: `away_price`, `home_price`, `start_ts`, `market_open_ts`
- **Key detail**: Opening price is fetched 60 seconds before game start time
- Contains TODO comments about graph functionality and market timing

### Team ID Mappings

**Baseball**: `baseball_api.py` contains a comprehensive `TEAM_ID_MAP` (line 13-44) mapping MLB team IDs to tuples of `(Full Name, Kalshi Abbreviation, Polymarket Abbreviation)`. This is critical for cross-platform data integration.

**Basketball**: Uses `nba_api.stats.static.teams` for team information and dynamically converts to abbreviations for Polymarket slugs.

### Application Layer (`backend/app/`)

Currently contains empty placeholder files:
- `main.py` - intended for application entry point
- `db.py` - intended for database operations

## Data Flow

1. **Schedule Fetching**: Service APIs first fetch game schedules for date ranges
2. **Stats Aggregation**: Cumulative team statistics are fetched for each game (prior to game date)
3. **Market Data Integration**: Betting market prices are fetched from Kalshi/Polymarket
4. **DataFrame Output**: All data is combined into pandas DataFrames with consistent column naming

## Important Implementation Details

### Async/Concurrency Patterns
- All service modules use `aiohttp.ClientSession` for concurrent HTTP requests
- Rate limiting is enforced via asyncio Semaphores and custom deque-based limiters
- Baseball API uses `tqdm_asyncio.gather()` for progress tracking (line 117)
- Basketball API uses `asyncio.create_task()` for gathering game data (line 280)

### Error Handling
- Services use try/except with retry logic and exponential backoff
- Failed requests return empty dicts/DataFrames rather than raising exceptions
- Baseball API filters out exceptions in results list (lines 120-126)
- Basketball API uses `return_exceptions=True` in gather() calls

### Date/Time Handling
- Game dates are `dt.date` objects
- Timestamps are Unix epoch integers (seconds)
- Opening prices are fetched 60 seconds before game start (`start_ts - 60`)
- Basketball module converts various date formats via `_as_datetime()` helper

### Data Filtering
- Baseball: Excludes games before May 1st, non-regular season, cancelled, doubleheaders
- Basketball: Regular season only (configurable via `season_type` parameter)

## Dependencies

Key packages from `requirements.txt`:
- `aiohttp` - async HTTP client
- `pandas` - data manipulation
- `nba_api` - NBA statistics API wrapper
- `requests` - synchronous HTTP (used by nba_api internally)
- `tqdm` - progress bars for async operations

## Notes for Future Development

1. The `main.py` and `db.py` files are empty - these likely need implementation for data persistence
2. Polymarket API contains TODOs about graphing functionality and market timing
3. Kalshi API has commented-out doubleheader handling logic that may need to be re-enabled
4. No frontend code exists yet - this is backend/data collection only
5. No testing infrastructure is present