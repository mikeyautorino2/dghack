# Polymarket Price Tracking System

A continuous monitoring system for NBA and NFL game markets on Polymarket. This system automatically discovers upcoming games, tracks their market prices every 5 minutes, and stores the data for historical analysis and candlestick visualization.

## System Overview

### Components

1. **Market Discovery Service** (`backend/scripts/discover_active_markets.py`)
   - Discovers upcoming NBA and NFL games
   - Checks if Polymarket markets exist for each game
   - Stores active markets in the database
   - Runs every 6 hours via cron

2. **Price Tracking Service** (`backend/scripts/track_market_prices.py`)
   - Fetches current prices for all active markets
   - Stores price snapshots with timestamp
   - Runs every 5 minutes via cron

3. **Database Schema** (`backend/app/db.py`)
   - `ActiveMarket` - Tracks currently active markets
   - `MarketPriceHistory` - Time series of price snapshots
   - `NBAGameFeatures` - Historical NBA games with stats
   - `NFLGameFeatures` - Historical NFL games with stats

4. **Polymarket API Enhancements** (`backend/services/polymarket_api.py`)
   - `get_current_price()` - Fetch current market price
   - `check_market_exists()` - Verify if market exists for a game
   - `get_opening_price()` - Fetch historical opening price (existing)

## Setup Instructions

### 1. Install Dependencies

```bash
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure Database

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/dghack
```

### 3. Create Database Tables

```python
python3 -c "from backend.app.db import Base, engine; Base.metadata.create_all(engine)"
```

### 4. Test Market Discovery

Run the market discovery script manually to populate initial markets:

```bash
python3 backend/scripts/discover_active_markets.py
```

### 5. Test Price Tracking

Run the price tracking script manually to verify it works:

```bash
python3 backend/scripts/track_market_prices.py
```

## Deployment to EC2

### Automated Setup

Use the provided setup script:

```bash
chmod +x backend/deploy/ec2_setup.sh
./backend/deploy/ec2_setup.sh
```

This script will:
- Install system dependencies (Python 3.11, PostgreSQL client, etc.)
- Set up Python virtual environment
- Install Python dependencies
- Create log directory
- Configure cron jobs
- Make scripts executable

### Manual Setup

If you prefer manual setup:

1. **Clone the repository**
   ```bash
   cd /home/ubuntu
   git clone <repository-url> dghack
   cd dghack
   ```

2. **Set up Python environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   nano .env
   # Add DATABASE_URL and other variables
   ```

4. **Create database tables**
   ```python
   python3 -c "from backend.app.db import Base, engine; Base.metadata.create_all(engine)"
   ```

5. **Make scripts executable**
   ```bash
   chmod +x backend/scripts/*.sh
   chmod +x backend/scripts/*.py
   ```

6. **Set up cron jobs**
   ```bash
   crontab -e
   ```

   Add these lines:
   ```
   # Price tracking every 5 minutes
   */5 * * * * /home/ubuntu/dghack/backend/scripts/run_price_tracker.sh >> /var/log/polymarket/price_tracker.log 2>&1

   # Market discovery every 6 hours
   0 */6 * * * /home/ubuntu/dghack/backend/scripts/run_market_discovery.sh >> /var/log/polymarket/market_discovery.log 2>&1
   ```

7. **Create log directory**
   ```bash
   sudo mkdir -p /var/log/polymarket
   sudo chown ubuntu:ubuntu /var/log/polymarket
   ```

## Monitoring

### View Logs

```bash
# Price tracking logs
tail -f /var/log/polymarket/price_tracker.log

# Market discovery logs
tail -f /var/log/polymarket/market_discovery.log
```

### Check Cron Jobs

```bash
crontab -l
```

### Verify Data Collection

```python
from backend.app.db import get_active_markets
markets = get_active_markets()
print(f"Tracking {len(markets)} active markets")
```

```sql
-- Check price history
SELECT market_id, COUNT(*) as snapshots,
       MIN(timestamp) as first_snapshot,
       MAX(timestamp) as last_snapshot
FROM market_price_history
GROUP BY market_id;
```

## Database Schema

### ActiveMarket Table

```python
- market_id (str, unique) - Polymarket market ID
- polymarket_slug (str) - URL slug format
- sport (str) - 'NBA' or 'NFL'
- game_date (date)
- away_team, home_team (str)
- away_team_id, home_team_id (str)
- game_start_ts (datetime) - When game starts
- market_open_ts (datetime) - When market opened
- market_close_ts (datetime) - When market closes
- market_status (str) - 'open', 'closed', 'resolved'
- last_updated (datetime) - Last price fetch
- created_at (datetime) - When discovered
```

### MarketPriceHistory Table

```python
- id (int, primary key)
- market_id (str, indexed) - References ActiveMarket
- timestamp (datetime, indexed) - When price observed
- away_price (float) - Away team win probability
- home_price (float) - Home team win probability
- mid_price (float) - Average of both prices
- volume (float, optional) - Trading volume
```

## API Usage Examples

### Get Current Price

```python
import asyncio
import aiohttp
from backend.services.polymarket_api import get_current_price
from datetime import date

async def main():
    async with aiohttp.ClientSession() as session:
        price = await get_current_price(
            session,
            sport="nfl",
            date=date(2024, 11, 10),
            away_team="giants",
            home_team="broncos"
        )
        print(f"Giants: {price['away_price']:.2%}")
        print(f"Broncos: {price['home_price']:.2%}")

asyncio.run(main())
```

### Check Market Exists

```python
from backend.services.polymarket_api import check_market_exists

async def main():
    async with aiohttp.ClientSession() as session:
        result = await check_market_exists(
            session,
            sport="nba",
            date=date(2024, 12, 25),
            away_team="lal",
            home_team="bos"
        )
        if result['exists']:
            print(f"Market ID: {result['market_id']}")
            print(f"Game starts: {result['game_start_ts']}")
```

### Insert Price Snapshot

```python
from backend.app.db import insert_price_snapshot
from datetime import datetime

success = insert_price_snapshot(
    market_id="market_123",
    timestamp=datetime.now(),
    away_price=0.45,
    home_price=0.55
)
```

### Get Active Markets

```python
from backend.app.db import get_active_markets

# Get all open markets
markets = get_active_markets(status='open')

for market in markets:
    print(f"{market['sport']}: {market['away_team']} @ {market['home_team']}")
    print(f"  Game date: {market['game_date']}")
    print(f"  Last updated: {market['last_updated']}")
```

## Troubleshooting

### Price tracking not running

1. Check if cron job is configured: `crontab -l`
2. Check if script is executable: `ls -la backend/scripts/*.sh`
3. Check logs: `tail -f /var/log/polymarket/price_tracker.log`
4. Test manually: `./backend/scripts/run_price_tracker.sh`

### No markets discovered

1. Verify database connection in `.env`
2. Check if upcoming games exist in NFL/NBA schedules
3. Verify Polymarket API is accessible
4. Run discovery manually with verbose output: `python3 backend/scripts/discover_active_markets.py`

### Database connection errors

1. Verify DATABASE_URL in `.env`
2. Check PostgreSQL is running and accessible
3. Verify database user has correct permissions
4. Test connection: `psql $DATABASE_URL`

## Next Steps

To complete the full website vision:

1. **Build KNN Similarity Engine**
   - Load historical games from NBA/NFLGameFeatures tables
   - Implement K-Nearest Neighbors on team statistics
   - Create function to find n most similar past matchups

2. **Build REST API** (FastAPI or Flask)
   - Endpoint to get upcoming games with current prices
   - Endpoint to get similar historical matchups for a game
   - Endpoint to get price history for candlestick charts

3. **Build Frontend**
   - List view of upcoming games with current prices
   - Detail view showing similar matchups
   - Candlestick chart visualization using price history

4. **Data Pipeline**
   - Backfill historical game data using existing APIs
   - Store in NBA/NFLGameFeatures tables for KNN training

## File Structure

```
backend/
├── app/
│   ├── db.py                           # Database models and functions
│   └── main.py                         # Future API entry point
├── services/
│   ├── basketball_api.py               # NBA data fetcher
│   ├── football_api.py                 # NFL data fetcher
│   ├── polymarket_api.py               # Polymarket API (enhanced)
│   └── kalshi_api.py                   # Kalshi API
├── scripts/
│   ├── discover_active_markets.py      # Market discovery service
│   ├── track_market_prices.py          # Price tracking service
│   ├── run_market_discovery.sh         # Discovery wrapper
│   └── run_price_tracker.sh            # Tracker wrapper
├── deploy/
│   └── ec2_setup.sh                    # EC2 deployment script
└── requirements.txt                     # Python dependencies
```

## Support

For issues or questions, check:
1. Logs in `/var/log/polymarket/`
2. Database tables for data integrity
3. Polymarket API status
4. Cron job execution times
