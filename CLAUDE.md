# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a sports betting analytics project that fetches historical game data and betting market prices from multiple sports (MLB, NBA, NFL) and prediction markets (Kalshi, Polymarket). The project aggregates cumulative team statistics with market pricing data to enable arbitrage detection and analytics.

## Product Goal

The end goal is to create a website where users can:

1. **View upcoming sports games** (NBA and NFL) that are available to bet on Polymarket
2. **See current market prices** for these upcoming games, continuously updated
3. **Click on a game** to view detailed analysis including:
   - Current Polymarket price and market details
   - Candlestick price charts from the **n most similar historical matchups** (configurable)
   - Similar matchups are determined using **K-Nearest Neighbors (KNN)** on cumulative team statistics

**Example Use Case**: If the Giants are playing the Broncos this upcoming Sunday, a user would see this game listed with its current Polymarket price. When they click on it, they'll see candlestick charts showing how betting markets evolved for the 5 (or n) most statistically similar Giants vs Broncos type matchups from historical data.

**Architecture Components**:
- **Historical Data**: Collected via service APIs (basketball_api.py, football_api.py, etc.)
- **Continuous Tracking**: System that monitors and updates current prices for active markets every 5 minutes
- **Similarity Engine**: KNN algorithm on team statistics to find historical comparables
- **Frontend**: Website displaying upcoming games, current prices, and historical candlestick visualizations

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
- Integrates with Polymarket for betting prices
- Main entry point: `get_historical_data_sync(start_date, end_date, fetch_market_data=True)`
- Returns DataFrame with **standardized columns**:
  - Game metadata: `game_id`, `game_date`, `away_team`, `away_team_id`, `home_team`, `home_team_id`
  - Hitting stats: `away_hitting_avg`, `away_hitting_obp`, `away_hitting_slg`, etc. (same for home)
  - Pitching stats: `away_pitching_era`, `away_pitching_whip`, `away_pitching_strikeoutsPer9Inn`, etc. (same for home)
  - Polymarket data: `polymarket_away_price`, `polymarket_home_price`, `polymarket_start_ts`, `polymarket_market_open_ts`, `polymarket_market_close_ts`
- Uses async/await with rate limiting via semaphores (max 10 concurrent requests)
- Filters out non-regular season games, cancelled games, and doubleheaders
- **Key detail**: Only processes games from May 1st onwards

#### `basketball_api.py`
- Fetches NBA team statistics using the `nba_api` library
- Integrates with Polymarket for betting prices
- Main entry point: `get_matchups_cumulative_stats_between(start_date, end_date)`
- Returns DataFrame with **standardized columns** (all lowercase):
  - Game metadata: `game_id`, `game_date`, `away_team`, `away_team_id`, `home_team`, `home_team_id`
  - Cumulative stats: `home_avg_pts`, `home_avg_reb`, `home_fg_pct`, etc. (same for away)
  - Polymarket data: `polymarket_away_price`, `polymarket_home_price`, `polymarket_start_ts`, `polymarket_market_open_ts`, `polymarket_market_close_ts`
- **Rate limiting**: 0.6 seconds between API calls
- **Key detail**: Fetches cumulative stats up to (but not including) the game date
- Uses helper `_get_team_info()` with caching to fetch team names from nba_api

#### `football_api.py`
- Fetches NFL game schedules and team statistics from ESPN API (`cdn.espn.com/core/nfl/schedule`)
- Integrates with Polymarket for betting prices
- Main entry point: `get_historical_data_sync(start_week, start_year, end_week, end_year)`
- Returns DataFrame with **standardized columns**:
  - Game metadata: `game_id`, `game_date`, `week`, `year`, `away_team`, `away_team_id`, `home_team`, `home_team_id`
  - Efficiency stats: `away_thirdDownEff`, `away_yardsPerPlay`, `away_yardsPerPass`, etc. (same for home)
  - Volume stats: `away_firstDowns`, `away_netPassingYards`, `away_rushingYards`, etc. (same for home)
  - Polymarket data: `polymarket_away_price`, `polymarket_home_price`, `polymarket_start_ts`, `polymarket_market_open_ts`, `polymarket_market_close_ts`
- Uses async/await with rate limiting via semaphores
- **Key detail**: Only processes games from week 4 onwards (needs weeks 1-3 for cumulative stats)

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
- **Main functions**:
  - `get_opening_price(session, sport, date, away_team, home_team)` - Fetches historical opening price (60s before game start)
  - `get_current_price(session, sport, date, away_team, home_team)` - Fetches current/live market price
  - `check_market_exists(session, sport, date, away_team, home_team)` - Verifies if market exists for a game
- Constructs market slug: `{sport}-{away_team}-{home_team}-{date}` (all lowercase)
- Returns dict with: `away_price`, `home_price`, `start_ts`, `market_open_ts`, `market_close_ts`
- **Key detail**: Opening price is fetched 60 seconds before game start time
- **Smart team order handling**: Tries both away-home and home-away order (Polymarket sometimes reverses teams)
- **Rate limiting**: 20 requests/second max with global deque-based rate limiter

### Team ID Mappings

**Baseball**: `baseball_api.py` contains a comprehensive `TEAM_ID_MAP` (line 13-44) mapping MLB team IDs to tuples of `(Full Name, Kalshi Abbreviation, Polymarket Abbreviation)`. This is critical for cross-platform data integration.

**Basketball**: Uses `nba_api.stats.static.teams` for team information and dynamically converts to abbreviations for Polymarket slugs.

### Application Layer (`backend/app/`)

#### `db.py` - Database Schema and Operations
Uses SQLAlchemy ORM with PostgreSQL for data persistence.

**Standardized Column Format** (all three sports):
All game tables share these common columns for consistency:
- `game_id` (String, primary key)
- `game_date` (Date)
- `home_team_id`, `away_team_id` (Integer)
- `home_team`, `away_team` (String) - Full team names
- `sport` (String) - 'NBA', 'NFL', or 'MLB'
- `season` (Integer)
- `polymarket_home_price`, `polymarket_away_price` (Float)
- `polymarket_start_ts`, `polymarket_market_open_ts`, `polymarket_market_close_ts` (DateTime)

**Tables**:

1. **`NBAGameFeatures`** (table: `games_features`)
   - Primary key: `game_id`
   - Contains 38 basketball statistics columns (avg_pts, avg_reb, fg_pct, etc.) for home/away teams
   - All columns use lowercase with underscores

2. **`NFLGameFeatures`** (table: `nfl_games_features`)
   - Primary key: `game_id`
   - Additional columns: `week`, `year`
   - Contains 22 football statistics columns (thirdDownEff, yardsPerPlay, etc.) for home/away teams

3. **`MLBGameFeatures`** (table: `mlb_games_features`)
   - Primary key: `game_id`
   - Contains 28 hitting statistics (hitting_avg, hitting_obp, etc.) for home/away teams
   - Contains 28 pitching statistics (pitching_era, pitching_whip, etc.) for home/away teams

4. **`ActiveMarket`** (table: `active_markets`)
   - Tracks which game markets are currently being monitored for price updates
   - Fields: market_id, sport, game_date, away_team, home_team, polymarket_slug, game_start_ts, market_status, last_updated

5. **`MarketPriceHistory`** (table: `market_price_history`)
   - Time series of price snapshots for active markets (updated every 5 minutes)
   - Fields: id, market_id, timestamp, away_price, home_price, mid_price

**Transformation Functions**:
- `prepare_nba_df_for_db()` - Adds sport/season columns, converts Unix timestamps to DateTime
- `prepare_nfl_df_for_db()` - Adds sport/season columns, converts Unix timestamps to DateTime
- `prepare_mlb_df_for_db()` - Adds sport/season columns, converts game_id to string, converts timestamps

**Insert Functions**:
- `insert_nba_games(df)` - Bulk inserts NBA historical data
- `insert_nfl_games(df)` - Bulk inserts NFL historical data
- `insert_mlb_games(df)` - Bulk inserts MLB historical data

**Market Tracking Functions**:
- `insert_active_markets(markets)` - Adds newly discovered markets to tracking
- `insert_price_snapshot(market_id, timestamp, away_price, home_price)` - Records a price observation
- `get_active_markets(status='open')` - Retrieves list of markets to track

#### `main.py`
Application entry point (to be implemented)

### Continuous Tracking System (`backend/scripts/`)

The continuous tracking system monitors active Polymarket markets for NBA and NFL games, updating prices every 5 minutes.

#### `discover_active_markets.py`
Discovers upcoming games and checks if Polymarket markets exist:
- Queries NFL schedule (upcoming games)
- Queries NBA schedule (upcoming games)
- For each game, checks if Polymarket market exists
- Stores active markets in `ActiveMarket` table
- Removes resolved/closed markets
- **Run frequency**: Every 6 hours via cron (markets typically open 1 day before games)

#### `track_market_prices.py`
Continuously tracks current prices for all active markets:
- Queries `ActiveMarket` table for list of markets to track
- Fetches current price from Polymarket for each market (with rate limiting)
- Calculates mid_price = (away_price + home_price) / 2
- Stores price snapshot in `MarketPriceHistory` table
- Updates `last_updated` timestamp in `ActiveMarket` table
- **Run frequency**: Every 5 minutes via cron

**Deployment**: Runs on EC2 instance with cron jobs for scheduled execution

## Usage Examples

### Collecting Historical Data

```python
from datetime import date
from backend.services import basketball_api, football_api, baseball_api
from backend.app import db

# Collect NBA data
nba_df = basketball_api.get_matchups_cumulative_stats_between(
    start_date=date(2024, 10, 1),
    end_date=date(2024, 11, 1)
)
rows = db.insert_nba_games(nba_df)
print(f"Inserted {rows} NBA games")

# Collect NFL data
nfl_df = football_api.get_historical_data_sync(
    start_week=4, start_year=2024,
    end_week=10, end_year=2024
)
rows = db.insert_nfl_games(nfl_df)
print(f"Inserted {rows} NFL games")

# Collect MLB data
mlb_df = baseball_api.get_historical_data_sync(
    start_date=date(2024, 5, 1),
    end_date=date(2024, 10, 1)
)
rows = db.insert_mlb_games(mlb_df)
print(f"Inserted {rows} MLB games")
```

### Creating Database Tables

```python
from backend.app.db import Base, engine

# Create all tables
Base.metadata.create_all(engine)

# Or drop and recreate (useful after schema changes)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
```

### Querying Market Data

```python
from backend.app.db import get_active_markets, SessionLocal, MarketPriceHistory

# Get all open markets
markets = get_active_markets(status='open')
for market in markets:
    print(f"{market['sport']}: {market['away_team']} @ {market['home_team']}")

# Query price history
session = SessionLocal()
prices = session.query(MarketPriceHistory).filter_by(
    market_id='some_market_id'
).order_by(MarketPriceHistory.timestamp).all()
session.close()
```

## Data Flow

### Historical Data Collection

1. **Schedule Fetching**: Service APIs first fetch game schedules for date ranges
2. **Stats Aggregation**: Cumulative team statistics are fetched for each game (prior to game date)
3. **Market Data Integration**: Betting market prices (opening prices) are fetched from Polymarket
4. **DataFrame Output**: All data is combined into pandas DataFrames with **standardized column naming**
5. **Transformation**: DataFrames are transformed via `prepare_*_df_for_db()` functions to add sport/season and convert timestamps
6. **Storage**: Data is inserted into database via `insert_*_games()` functions

### Continuous Price Tracking

1. **Market Discovery** (every 6 hours): `discover_active_markets.py` queries upcoming games and checks if Polymarket markets exist
2. **Price Tracking** (every 5 minutes): `track_market_prices.py` fetches current prices for all active markets
3. **Storage**: Price snapshots are stored in `MarketPriceHistory` table for candlestick visualization

### Standardized Column Format

All three sports APIs now return DataFrames with consistent naming:
- **Game metadata**: `game_id`, `game_date`, `home_team`, `home_team_id`, `away_team`, `away_team_id` (all lowercase)
- **Team IDs**: Always integers
- **Polymarket data**: `polymarket_away_price`, `polymarket_home_price`, `polymarket_start_ts`, `polymarket_market_open_ts`, `polymarket_market_close_ts`
- **Timestamps**: Unix epoch integers in API output, converted to DateTime objects in database

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
- `aiohttp==3.13.2` - async HTTP client
- `pandas==2.3.3` - data manipulation
- `nba_api==1.10.2` - NBA statistics API wrapper
- `requests==2.32.5` - synchronous HTTP (used by nba_api internally)
- `tqdm==4.67.1` - progress bars for async operations
- `SQLAlchemy==2.0.36` - ORM for database operations
- `psycopg2-binary==2.9.10` - PostgreSQL adapter
- `python-dotenv==1.0.1` - environment variable management
- `scikit-learn==1.7.2` - machine learning (for future KNN implementation)
- `numpy==2.3.4` - numerical computing

## Schema Standardization (Completed)

All three sports (NBA, NFL, MLB) have been standardized to use consistent:
- Column naming conventions (lowercase with underscores)
- Team ID types (Integer)
- Primary keys (game_id as String)
- Polymarket pricing columns (polymarket_away_price, polymarket_home_price, etc.)
- Team name columns (home_team, away_team)

This standardization enables:
- Easy comparison and analysis across sports
- Unified KNN similarity engine implementation
- Consistent data pipeline and storage patterns

## Next Steps for Development

1. **KNN Similarity Engine**: Implement algorithm to find n most similar historical matchups based on team statistics
2. **REST API**: Build FastAPI backend with endpoints for:
   - Get upcoming games with current prices
   - Get similar historical matchups for a game
   - Get price history for candlestick visualization
3. **Frontend**: Build React/Next.js website with:
   - List view of upcoming games
   - Detail view with similar matchups
   - Candlestick chart components
4. **Historical Data Backfill**: Run data collection scripts to populate NBA/NFL/MLB tables with past seasons
5. **Testing Infrastructure**: Add unit tests and integration tests for APIs and database functions
6. **Deployment Automation**: Enhance EC2 setup with infrastructure-as-code (Terraform/CloudFormation)

## Important Notes

1. **Database Migration Required**: If tables already exist, they must be dropped and recreated with new schemas (column names and types changed)
2. **Basketball API Change**: Now returns lowercase columns instead of uppercase (breaking change if old code depends on uppercase)
3. **MLB Support**: Full MLB schema and insert functions now available (previously not implemented)
4. **Continuous Tracking**: Price tracking system is ready for deployment on EC2 with cron jobs