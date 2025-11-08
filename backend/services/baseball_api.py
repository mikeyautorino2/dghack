import aiohttp
import asyncio
import datetime as dt
import pandas as pd
from typing import List, Dict, Optional
from tqdm.asyncio import tqdm_asyncio

import polymarket_api as polyapi

# MLB team ID: (Full Name, [Unused - was Kalshi], Polymarket Abbreviation)
TEAM_ID_MAP = {
    133: ("Athletics", "ATH", "oak"),
    134: ("Pittsburgh Pirates", "PIT", "pit"),
    135: ("San Diego Padres", "SD", "sd"),
    136: ("Seattle Mariners", "SEA", "sea"),
    137: ("San Francisco Giants", "SF", "sf"),
    138: ("St. Louis Cardinals", "STL", "stl"),
    139: ("Tampa Bay Rays", "TB", "tb"),
    140: ("Texas Rangers", "TEX", "tex"),
    141: ("Toronto Blue Jays", "TOR", "tor"),
    142: ("Minnesota Twins", "MIN", "min"),
    143: ("Philadelphia Phillies", "PHI", "phi"),
    144: ("Atlanta Braves", "ATL", "atl"),
    145: ("Chicago White Sox", "CWS", "cws"), 
    146: ("Miami Marlins", "MIA", "mia"),
    147: ("New York Yankees", "NYY", "nyy"),
    158: ("Milwaukee Brewers", "MIL", "mil"),
    108: ("Los Angeles Angels", "LAA", "laa"),
    109: ("Arizona Diamondbacks", "AZ", "ari"),
    110: ("Baltimore Orioles", "BAL", "bal"),
    111: ("Boston Red Sox", "BOS", "bos"),
    112: ("Chicago Cubs", "CHC", "chc"),
    113: ("Cincinnati Reds", "CIN", "cin"),
    114: ("Cleveland Guardians", "CLE", "cle"),
    115: ("Colorado Rockies", "COL", "col"),
    116: ("Detroit Tigers", "DET", "det"),
    117: ("Houston Astros", "HOU", "hou"),
    118: ("Kansas City Royals", "KC", "kc"),
    119: ("Los Angeles Dodgers", "LAD", "lad"),
    120: ("Washington Nationals", "WSH", "wsh"),
    121: ("New York Mets", "NYM", "nym")
}

async def get_historical_data(start_date: dt.date, end_date: dt.date,
                              max_concurrent: int = 10,
                              fetch_market_data: bool = True) -> pd.DataFrame:
    """Fetch historical MLB game data with team stats and optionally market data.

    Args:
        start_date: Start date for game data
        end_date: End date for game data
        max_concurrent: Maximum number of concurrent stat requests
        fetch_market_data: Whether to fetch Polymarket market data
    """
    
    # Get the schedule
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            schedule_data = await response.json()
    
    # Parse games
    games_to_fetch = []
    for d in schedule_data.get("dates", []):
        the_date = dt.date.fromisoformat(d["date"])
        if the_date < dt.date(the_date.year, 5, 1):
            continue
        
        for game in d["games"]:
            # only want regular and non-cancelled games
            if game["gameType"] != "R" or game["status"]["codedGameState"] == "C":
                continue
            
            # skip doubleheaders
            if game.get("doubleHeader", "N") in ["Y", "S"]:
                continue
            
            away_team = game["teams"]["away"]["team"]
            home_team = game["teams"]["home"]["team"]
            
            games_to_fetch.append({
                "game_id": game["gamePk"],
                "date": the_date,
                "away": away_team["name"],
                "home": home_team["name"],
                "away_id": away_team["id"],
                "home_id": home_team["id"]
            })
    
    print(f"Found {len(games_to_fetch)} games to fetch")
    
    # Fetch all stats with concurrency control
    async with aiohttp.ClientSession() as session:
        rows = await fetch_all_game_stats(session, games_to_fetch, max_concurrent, fetch_market_data)
    
    return pd.DataFrame(rows) #.dropna() # occasionally, Polymarket api fails so get useless NaN vals


async def fetch_all_game_stats(session: aiohttp.ClientSession, 
                               games: List[Dict], 
                               max_concurrent: int, 
                               fetch_market_data: bool) -> List[Dict]:
    """Fetch stats for all games with concurrency control."""
    if not games:
        return []
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_limit(game):
        async with semaphore:
            return await fetch_game_stats(session, game, fetch_market_data)
    
    tasks = [fetch_with_limit(game) for game in games]
    results = await tqdm_asyncio.gather(*tasks, desc="Fetching games")
    
    # Filter out failures
    rows = []
    for i, result in enumerate(results):
        if isinstance(result, dict):
            rows.append(result)
        else:
            print(f"Error fetching game {games[i]['game_id']}: {result}")
    
    return rows


async def fetch_game_stats(session: aiohttp.ClientSession, 
                           game_info: Dict, 
                           fetch_market: bool) -> Dict:
    """Fetch all stats for a single game."""
    
    game_date = game_info["date"]
    away_id = game_info["away_id"]
    home_id = game_info["home_id"]
    
    # Fetch 4 stat requests concurrently
    tasks = [
        fetch_team_stats(session, away_id, "hitting", game_date),
        fetch_team_stats(session, away_id, "pitching", game_date),
        fetch_team_stats(session, home_id, "hitting", game_date),
        fetch_team_stats(session, home_id, "pitching", game_date)
    ]
    
    try:
        away_hitting, away_pitching, home_hitting, home_pitching = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        if isinstance(away_hitting, Exception):
            away_hitting = {}
        if isinstance(away_pitching, Exception):
            away_pitching = {}
        if isinstance(home_hitting, Exception):
            home_hitting = {}
        if isinstance(home_pitching, Exception):
            home_pitching = {}
    except Exception as e:
        print(f"Error fetching stats for game {game_info['game_id']}: {e}")
        away_hitting = away_pitching = home_hitting = home_pitching = {}
    
    # Build row
    row = {
        "game_id": game_info["game_id"],
        "game_date": game_info["date"],
        "away_team": game_info["away"],
        "away_team_id": game_info["away_id"],
        "home_team": game_info["home"],
        "home_team_id": game_info["home_id"]
    }
    
    flatten_stats(row, away_hitting, "away_hitting")
    flatten_stats(row, away_pitching, "away_pitching")
    flatten_stats(row, home_hitting, "home_hitting")
    flatten_stats(row, home_pitching, "home_pitching")
    
    # Fetch market data if requested
    if fetch_market:
        away_poly = TEAM_ID_MAP.get(away_id, (None, None, None))[2]
        home_poly = TEAM_ID_MAP.get(home_id, (None, None, None))[2]

        if away_poly and home_poly:
            market_data = await polyapi.get_opening_price(
                session,
                sport="mlb",
                date=game_date,
                away_team=away_poly,
                home_team=home_poly
            )

            row["polymarket_away_price"] = market_data.get("away_price")
            row["polymarket_home_price"] = market_data.get("home_price")
            row["polymarket_start_ts"] = market_data.get("start_ts")
            row["polymarket_market_open_ts"] = market_data.get("market_open_ts")
            row["polymarket_market_close_ts"] = market_data.get("market_close_ts")
    
    return row


async def fetch_team_stats(session: aiohttp.ClientSession, 
                           team_id: int, 
                           group: str, 
                           game_date: dt.date) -> Dict:
    """Fetch stats for a single team/group/date combination."""
    
    year_begin = dt.date(game_date.year, 1, 1).strftime("%m/%d/%Y")
    day_before = (game_date - dt.timedelta(days=1)).strftime("%m/%d/%Y")
    
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?group={group}&sportIds=1&stats=byDateRange&startDate={year_begin}&endDate={day_before}"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            data = await response.json()
            
            if not data.get("stats") or not data["stats"][0].get("splits"):
                return {}
            
            stats = data["stats"][0]["splits"][0]["stat"]
            
    except Exception as e:
        print(f"Error fetching {group} stats for team {team_id} on {game_date}: {e}")
        return {}
    
    # Extract relevant stats
    if group == "hitting":
        stat_list = ["avg", "obp", "slg", "ops", "stolenBasePercentage", "babip", "groundOutsToAirouts", "atBatsPerHomeRun"]
    elif group == "pitching":
        stat_list = ["avg", "obp", "slg", "ops", "stolenBasePercentage", "era", "whip", "groundOutsToAirouts", 
                     "pitchesPerInning", "strikeoutsPer9Inn", "walksPer9Inn", "hitsPer9Inn", "runsScoredPer9", "homeRunsPer9"]
    else:
        return {}
    
    result = {}
    for stat in stat_list:
        if stat in stats and stats[stat] not in (None, "-.--", ""):
            try:
                result[stat] = float(stats[stat])
            except (ValueError, TypeError):
                pass
    
    return result


def flatten_stats(row_dict: Dict, stats_dict: Dict, prefix: str) -> None:
    """Add stats from stats_dict to row_dict with the given prefix."""
    for stat, value in stats_dict.items():
        row_dict[f"{prefix}_{stat}"] = value


def get_historical_data_sync(start_date: dt.date, end_date: dt.date, fetch_market_data: bool = True) -> pd.DataFrame:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_historical_data(start_date, end_date, fetch_market_data=fetch_market_data))


if __name__ == "__main__":
    import time
    
    start_date = dt.date(2024, 5, 1)
    end_date = dt.date(2024, 5, 3)
    
    print(f"Fetching games from {start_date} to {end_date}...")
    start_time = time.time()
    
    df = get_historical_data_sync(start_date, end_date, fetch_market_data=True)
    
    elapsed = time.time() - start_time
    print(f"\nFetched {len(df)} games in {elapsed:.2f} seconds")
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nFirst game:\n{df.iloc[0] if len(df) > 0 else 'No games found'}")