# Backend Scripts

This directory contains utility scripts for managing the sports betting analytics database.

## Data Collection Scripts

### `backfill_historical_data.py`

Backfills the database with historical game data from multiple seasons.

**Data Collected:**
- **NBA**: Oct 18, 2022 → Present (2022-23, 2023-24, 2024-25 seasons)
- **NFL**: Week 1 2023 → Present (2023, 2024 seasons)
  - Note: API only returns Week 4+ games (needs weeks 1-3 for cumulative stats)
- **MLB**: May 1, 2022 → Present (2022, 2023, 2024 seasons)
  - Note: API constraint prevents games before May 1st

**Usage:**
```bash
# Activate virtual environment
source venv/bin/activate

# Ensure database tables exist
python3 -c "from backend.app.db import Base, engine; Base.metadata.create_all(engine)"

# Run backfill
python3 backend/scripts/backfill_historical_data.py
```

**What it does:**
1. Fetches game data from respective sports APIs
2. Retrieves team statistics and Polymarket pricing data
3. Transforms data to match database schema
4. Inserts data into PostgreSQL database

**Expected Duration:** 10-30 minutes depending on API response times and rate limiting

**Output:**
```
Overall Progress: 33%|████████           | 1/3 [05:23<10:46, 323.15s/sport]
NBA Seasons: 100%|████████████████████| 3/3 [05:23<00:00, 107.72s/season]
  ✓ Inserted 1230 games for 2022-23
  ✓ Inserted 1230 games for 2023-24
  ✓ Inserted 230 games for 2024-25 (current)

Overall Progress: 67%|████████████       | 2/3 [08:15<04:07, 247.34s/sport]
NFL Seasons: 100%|████████████████████| 2/2 [02:52<00:00, 86.12s/season]
  ✓ Inserted 255 games for 2023
  ✓ Inserted 255 games for 2024
...
```

**Progress Tracking:**
- Overall progress bar shows completion across all 3 sports
- Individual progress bars for each sport's seasons
- Real-time statistics on games inserted

---

### `verify_database.py`

Verifies database contents and displays statistics.

**Usage:**
```bash
python3 backend/scripts/verify_database.py
```

**Output:**
```
DATABASE VERIFICATION
======================================================================

NBA (nba_games_features)
----------------------------------------------------------------------
  Total games: 3690
  Breakdown by season:
    2022-23: 1230 games
    2023-24: 1230 games
    2024-25: 230 games
  Date range: 2022-10-18 to 2024-11-08

NFL (nfl_games_features)
----------------------------------------------------------------------
  Total games: 510
  Breakdown by season:
    2023: 255 games
    2024: 255 games
  Week range: Week 4 to Week 18
  Date range: 2023-09-28 to 2024-11-08

MLB (mlb_games_features)
----------------------------------------------------------------------
  Total games: 4860
  Breakdown by season:
    2022: 1620 games
    2023: 1620 games
    2024: 1620 games
  Date range: 2022-05-01 to 2024-10-31

======================================================================
SUMMARY
======================================================================
  Total games in database: 9060
    • NBA: 3690
    • NFL: 510
    • MLB: 4860
```

---

## Market Tracking Scripts

### `discover_active_markets.py`

Discovers upcoming NBA/NFL games and checks if Polymarket markets exist.

**Usage:**
```bash
python3 backend/scripts/discover_active_markets.py
```

**Run frequency:** Every 6 hours via cron

---

### `track_market_prices.py`

Tracks current prices for all active Polymarket markets.

**Usage:**
```bash
python3 backend/scripts/track_market_prices.py
```

**Run frequency:** Every 5 minutes via cron

---

## Shell Wrappers

### `run_market_discovery.sh`

Wrapper script for market discovery with logging and error handling.

**Cron setup:**
```bash
0 */6 * * * /path/to/dghack/backend/scripts/run_market_discovery.sh >> /var/log/polymarket/market_discovery.log 2>&1
```

---

### `run_price_tracker.sh`

Wrapper script for price tracking with logging and error handling.

**Cron setup:**
```bash
*/5 * * * * /path/to/dghack/backend/scripts/run_price_tracker.sh >> /var/log/polymarket/price_tracker.log 2>&1
```

---

## Prerequisites

Before running any scripts:

1. **Database setup:**
   ```bash
   # Create .env file with DATABASE_URL
   echo "DATABASE_URL=postgresql://user:pass@localhost:5432/dghack" > .env

   # Create tables
   python3 -c "from backend.app.db import Base, engine; Base.metadata.create_all(engine)"
   ```

2. **Virtual environment:**
   ```bash
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Environment variables:**
   - `DATABASE_URL`: PostgreSQL connection string

---

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'backend'`**
- Make sure you're running from the project root: `/Users/arnsar/projects/dghack/`
- Scripts automatically add backend to path

**Error: `sqlalchemy.exc.OperationalError`**
- Check DATABASE_URL in `.env`
- Verify PostgreSQL is running
- Test connection: `psql $DATABASE_URL`

**Error: `DuplicateKeyError`**
- You're trying to insert games that already exist
- Delete old data or run verification script to check what's already in DB

**API rate limiting errors:**
- Scripts respect rate limits automatically
- If errors persist, increase delays in the API modules

---

## Expected Game Counts

**NBA (per season):**
- Regular season: ~1,230 games (30 teams × 82 games / 2)

**NFL (per season):**
- Weeks 4-18: ~255 games (from Week 4 onwards due to API constraint)

**MLB (per season, May-Oct):**
- May-October: ~1,620 games (30 teams × 162 games / 3)
