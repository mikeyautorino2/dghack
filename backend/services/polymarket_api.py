import datetime as dt
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import asyncio
import aiohttp
import json
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
    slug = f"{sport.lower()}-{away_team.lower()}-{home_team.lower()}-{date.strftime('%Y-%m-%d')}"
    market_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    opening_price_url = "https://clob.polymarket.com/prices-history"

    async with session.get(market_url) as response:
        data = await response.json()

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

    async with session.get(opening_price_url, params=queryString) as res:
        info = await res.json()

    away = info["history"][0]["p"]
    home = 1.0 - away

    return {
        "away_price": away,
        "home_price": home,
        "start_ts": start_ts,
        "market_open_ts": market_open
    }
"""
nba = "nba"
away = "sac"
home = "den"
date = dt.date(2025, 11, 4)
#print(asyncio.run(get_opening_price(nba, date, away, home)))
"""

#testing, use /prices-history and set the startTs (time that the event started) to be the time when the market started
#clobID for a team, so then u can find Team B opening prices by doing 1 - teamA opening price in singular funciton
""""

for a start time of -> start_time = 1762131600 UTC 
data = {
    "history": [
        {"t": 1762131618, "p": 0.625},
        {"t": 1762131666, "p": 0.62},
        {"t": 1762131726, "p": 0.615},
        # ... (rest of your data)
    ]
}

start_time = 1762131600  # game start timestamp

# Find the last price before or equal to start_time
pre_event = max(
    (point for point in data["history"] if point["t"] <= start_time),
    key=lambda x: x["t"],
    default=None
)


(GPT bullshit)
if pre_event:
    print(f"Pre-event price: {pre_event['p']} at t={pre_event['t']}")
else:
    print("⚠️ No data point found before the start time.")

    
this code would return -> {"t":1762131618,"p":0.625} (real opening price was 0.63 for the red wings right when event started)

"""
