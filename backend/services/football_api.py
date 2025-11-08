import aiohttp
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from typing import List, Dict, Optional
from tqdm.asyncio import tqdm_asyncio

import polymarket_api as polyapi

# NFL team ID: (Full Name, [Unused - was Kalshi], Polymarket Abbreviation)
TEAM_ID_MAP = {
    1: ("Atlanta Falcons", "ATL", "atl"),
    2: ("Buffalo Bills", "BUF", "buf"),
    3: ("Chicago Bears", "CHI", "chi"),
    4: ("Cincinnati Bengals", "CIN", "cin"),
    5: ("Cleveland Browns", "CLE", "cle"),
    6: ("Dallas Cowboys", "DAL", "dal"),
    7: ("Denver Broncos", "DEN", "den"),
    8: ("Detroit Lions", "DET", "det"),
    9: ("Green Bay Packers", "GB", "gb"),
    10: ("Tennessee Titans", "TEN", "ten"),
    11: ("Indianapolis Colts", "IND", "ind"),
    12: ("Kansas City Chiefs", "KC", "kc"),
    13: ("Las Vegas Raiders", "LV", "lv"),
    14: ("Los Angeles Rams", "LA", "la"),
    15: ("Miami Dolphins", "MIA", "mia"),
    16: ("Minnesota Vikings", "MIN", "min"),
    17: ("New England Patriots", "NE", "ne"),
    18: ("New Orleans Saints", "NO", "no"),
    19: ("New York Giants", "NYG", "nyg"),
    20: ("New York Jets", "NYJ", "nyj"),
    21: ("Philadelphia Eagles", "PHI", "phi"),
    22: ("Arizona Cardinals", "ARI", "ari"),
    23: ("Pittsburgh Steelers", "PIT", "pit"),
    24: ("Los Angeles Chargers", "LAC", "lac"),
    25: ("San Francisco 49ers", "SF", "sf"),
    26: ("Seattle Seahawks", "SEA", "sea"),
    27: ("Tampa Bay Buccaneers", "TB", "tb"),
    28: ("Washington Commanders", "WAS", "was"),
    29: ("Carolina Panthers", "CAR", "car"),
    30: ("Jacksonville Jaguars", "JAC", "jax"),
    33: ("Baltimore Ravens", "BAL", "bal"),
    34: ("Houston Texans", "HOU", "hou"),
}


async def fetch_schedule(session: aiohttp.ClientSession, year: int, week: int) -> List[Dict]:
    """Fetch schedule for a specific year/week. Returns list of game dicts."""
    url = f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={year}&week={week}"

    try:
        async with session.get(url) as response:
            data = await response.json()

        schedule_data = data.get("content", {}).get("schedule", {})
        games = []

        for _, date_data in schedule_data.items():
            for game in date_data.get("games", []):
                # Validate structure
                if not game.get("competitions") or len(game["competitions"]) == 0:
                    continue

                competition = game["competitions"][0]
                if not competition.get("competitors") or len(competition["competitors"]) < 2:
                    continue

                event_id = competition.get("id")
                if not event_id:
                    continue

                # Extract team info
                competitors = competition["competitors"]
                home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)

                if not home_team or not away_team:
                    continue

                try:
                    game_date_str = game.get("date")
                    # Parse as UTC datetime
                    game_datetime_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                    # Convert to US Eastern time to get the correct local game date
                    game_datetime_et = game_datetime_utc.astimezone(ZoneInfo("America/New_York"))
                    game_date = game_datetime_et.date()

                    games.append({
                        "game_id": event_id,
                        "date": game_date,
                        "week": week,
                        "year": year,
                        "away_id": int(away_team["id"]),
                        "home_id": int(home_team["id"]),
                        "away_name": away_team.get("team", {}).get("displayName", "Unknown"),
                        "home_name": home_team.get("team", {}).get("displayName", "Unknown")
                    })
                except (ValueError, KeyError) as e:
                    print(f"Error parsing game {event_id}: {e}")
                    continue

        return games
    except Exception as e:
        print(f"Error fetching schedule for {year} week {week}: {e}")
        return []


async def fetch_team_game_stats(session: aiohttp.ClientSession, event_id: str, team_id: int) -> Dict[str, float]:
    """Fetch team statistics for a specific game. Returns dict of stat_name: value."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"

    # Whitelist of statistics to keep
    ALLOWED_STATS = {
        # Efficiency metrics (good for similarity)
        "thirdDownEff",
        "fourthDownEff",
        "yardsPerPlay",
        "yardsPerPass",
        "yardsPerRushAttempt",
        "redZoneAttempts",
        # Volume metrics (kept for normalization)
        "firstDowns",
        "netPassingYards",
        "rushingYards",
        "interceptions",
        "fumblesLost"
    }

    try:
        async with session.get(url) as response:
            data = await response.json()

        teams = data.get("boxscore", {}).get("teams", [])

        # Find the team by ID
        team_data = None
        for team in teams:
            if team.get("team", {}).get("id") == str(team_id):
                team_data = team
                break

        if not team_data:
            return {}

        # Extract only whitelisted statistics
        statistics = team_data.get("statistics", [])
        stats_dict = {}

        for stat in statistics:
            stat_name = stat.get("name")
            stat_value = stat.get("value")

            # Only process whitelisted stats
            if stat_name in ALLOWED_STATS and stat_value is not None:
                # Try to convert to float, skip if it's a string like "-" or "N/A"
                if isinstance(stat_value, (int, float)):
                    stats_dict[stat_name] = float(stat_value)
                elif isinstance(stat_value, str) and stat_value not in ["-", "N/A", ""]:
                    try:
                        stats_dict[stat_name] = float(stat_value)
                    except ValueError:
                        # Skip non-numeric values
                        pass

        return stats_dict
    except Exception as e:
        print(f"Error fetching stats for event {event_id}, team {team_id}: {e}")
        return {}


async def get_team_cumulative_stats(session: aiohttp.ClientSession, team_id: int,
                                    year: int, week: int) -> Dict[str, Optional[float]]:
    """Calculate cumulative per-game stats for a team up to (not including) a specific game.
    Includes data from weeks 1-3 in calculations, but only for games in week 4+."""

    # Fetch all games for this team from weeks 1 through (week-1)
    # This includes weeks 1-3 data for calculating week 4+ stats
    all_previous_games = []

    for prev_week in range(1, week):
        games = await fetch_schedule(session, year, prev_week)

        # Find games involving this team
        for game in games:
            if game["away_id"] == team_id or game["home_id"] == team_id:
                all_previous_games.append(game)

    if not all_previous_games:
        # No previous games found, return empty stats
        return {}

    # Fetch stats for all previous games
    stat_totals = {}
    games_with_stats = 0

    for game in all_previous_games:
        game_stats = await fetch_team_game_stats(session, game["game_id"], team_id)

        if game_stats:
            games_with_stats += 1
            for stat_name, stat_value in game_stats.items():
                if stat_name not in stat_totals:
                    stat_totals[stat_name] = 0.0
                stat_totals[stat_name] += stat_value

    if games_with_stats == 0:
        return {}

    # Calculate per-game averages
    per_game_stats = {}
    for stat_name, total in stat_totals.items():
        per_game_stats[stat_name] = total / games_with_stats

    return per_game_stats


async def fetch_game_stats(session: aiohttp.ClientSession, game_info: Dict, fetch_market: bool = True) -> Dict:
    """Fetch all stats for a single game including cumulative team stats and Polymarket data."""

    event_id = game_info["game_id"]
    game_date = game_info["date"]
    away_id = game_info["away_id"]
    home_id = game_info["home_id"]
    week = game_info["week"]
    year = game_info["year"]

    try:
        # Fetch cumulative stats for both teams
        away_stats, home_stats = await asyncio.gather(
            get_team_cumulative_stats(session, away_id, year, week),
            get_team_cumulative_stats(session, home_id, year, week),
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(away_stats, Exception):
            print(f"Error fetching away stats for game {event_id}: {away_stats}")
            away_stats = {}
        if isinstance(home_stats, Exception):
            print(f"Error fetching home stats for game {event_id}: {home_stats}")
            home_stats = {}

        # Build row
        row = {
            "game_id": event_id,
            "game_date": game_date,
            "week": week,
            "year": year,
            "away_team": game_info["away_name"],
            "away_team_id": away_id,
            "home_team": game_info["home_name"],
            "home_team_id": home_id
        }

        # Add cumulative stats with prefixes
        for stat_name, stat_value in away_stats.items():
            row[f"away_{stat_name}"] = stat_value
        for stat_name, stat_value in home_stats.items():
            row[f"home_{stat_name}"] = stat_value

        # Fetch Polymarket data if requested
        if fetch_market:
            away_poly = TEAM_ID_MAP.get(away_id, (None, None, None))[2]
            home_poly = TEAM_ID_MAP.get(home_id, (None, None, None))[2]

            if away_poly and home_poly:
                market_data = await polyapi.get_opening_price(
                    session,
                    sport="nfl",
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
    except Exception as e:
        print(f"Error fetching game stats for {event_id}: {e}")
        return {}


async def fetch_all_game_stats(session: aiohttp.ClientSession, games: List[Dict],
                               max_concurrent: int, fetch_market_data: bool) -> List[Dict]:
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
        if isinstance(result, dict) and result:
            rows.append(result)
        elif isinstance(result, Exception):
            print(f"Error fetching game {games[i]['game_id']}: {result}")

    return rows


async def get_historical_data(start_week: int, start_year: int,
                              end_week: int, end_year: int,
                              max_concurrent: int = 5,
                              fetch_market_data: bool = True) -> pd.DataFrame:
    """Fetch historical NFL game data with team stats and optionally market data.

    Args:
        start_week: Starting week number (1-18)
        start_year: Starting year (e.g., 2024)
        end_week: Ending week number (1-18)
        end_year: Ending year (e.g., 2024)
        max_concurrent: Maximum number of concurrent requests
        fetch_market_data: Whether to fetch Polymarket market data

    Returns:
        DataFrame with game data, cumulative per-game team stats, and market data.
        Only includes games from week 4 onwards.
    """

    # Create session for all requests
    async with aiohttp.ClientSession() as session:
        # Collect all (year, week) pairs to fetch
        # IMPORTANT: Always fetch from week 1 to calculate cumulative stats correctly
        weeks_to_fetch = []

        if start_year == end_year:
            # Same season - fetch from week 1 through end_week
            for week in range(1, end_week + 1):
                weeks_to_fetch.append((start_year, week))
        else:
            # Span multiple seasons
            # Fetch all weeks of start year (starting from week 1)
            for week in range(1, 19):  # NFL regular season is usually 18 weeks
                weeks_to_fetch.append((start_year, week))

            # Fetch all intermediate years (full 18 weeks each)
            for year in range(start_year + 1, end_year):
                for week in range(1, 19):
                    weeks_to_fetch.append((year, week))

            # Fetch weeks 1 through end_week of end year
            for week in range(1, end_week + 1):
                weeks_to_fetch.append((end_year, week))

        # Fetch schedules for all weeks
        schedule_tasks = [fetch_schedule(session, year, week) for year, week in weeks_to_fetch]
        all_schedules = await asyncio.gather(*schedule_tasks)

        # Flatten all games and filter to only include games from start_week onwards and week >= 4
        all_games = []
        for games in all_schedules:
            for game in games:
                # Only include games from week 4+, and from start_week onwards
                if game["week"] >= 4:
                    # Check if game is within the requested range
                    if start_year == end_year:
                        if start_week <= game["week"] <= end_week:
                            all_games.append(game)
                    else:
                        # Multi-season: include if in start year (>= start_week) or end year (<= end_week)
                        if (game["year"] == start_year and game["week"] >= start_week) or \
                        (start_year < game["year"] < end_year) or \
                        (game["year"] == end_year and game["week"] <= end_week):
                            all_games.append(game)

        print(f"Found {len(all_games)} games to fetch (filtered to weeks {start_week}-{end_week}, week >= 4)")

        if not all_games:
            return pd.DataFrame()

        # Fetch stats for all games
        rows = await fetch_all_game_stats(session, all_games, max_concurrent, fetch_market_data)

    # Filter out games with missing Polymarket data (some games don't have markets)
    return pd.DataFrame(rows).dropna()


def get_historical_data_sync(start_week: int, start_year: int,
                             end_week: int, end_year: int,
                             fetch_market_data: bool = True) -> pd.DataFrame:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_historical_data(start_week, start_year, end_week, end_year,
                                          fetch_market_data=fetch_market_data))


if __name__ == "__main__":
    import time

    # Test with Weeks 5-6 of 2024 season
    start_week = 5
    start_year = 2024
    end_week = 6
    end_year = 2024

    print(f"Fetching games from Week {start_week} ({start_year}) to Week {end_week} ({end_year})...")
    start_time = time.time()

    df = get_historical_data_sync(start_week, start_year, end_week, end_year, fetch_market_data=True)

    elapsed = time.time() - start_time
    print(f"\nFetched {len(df)} games in {elapsed:.2f} seconds")
    print(f"\nColumns: {df.columns.tolist()}")
    if len(df) > 0:
        print(f"\nFirst game:\n{df.iloc[0]}")