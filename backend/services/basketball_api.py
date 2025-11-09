import aiohttp
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from typing import List, Dict, Optional
from tqdm.asyncio import tqdm_asyncio

from . import polymarket_api as polyapi

# NBA team ID: (Full Name, [Unused], Polymarket Abbreviation)
TEAM_ID_MAP = {
    1: ("Atlanta Hawks", "---", "atl"),
    2: ("Boston Celtics", "---", "bos"),
    3: ("New Orleans Pelicans", "---", "nop"),
    4: ("Chicago Bulls", "---", "chi"),
    5: ("Cleveland Cavaliers", "---", "cle"),
    6: ("Dallas Mavericks", "---", "dal"),
    7: ("Denver Nuggets", "---", "den"),
    8: ("Detroit Pistons", "---", "det"),
    9: ("Golden State Warriors", "---", "gsw"),
    10: ("Houston Rockets", "---", "hou"),
    11: ("Indiana Pacers", "---", "ind"),
    12: ("LA Clippers", "---", "lac"),
    13: ("Los Angeles Lakers", "---", "lal"),
    14: ("Miami Heat", "---", "mia"),
    15: ("Milwaukee Bucks", "---", "mil"),
    16: ("Minnesota Timberwolves", "---", "min"),
    17: ("Brooklyn Nets", "---", "bkn"),
    18: ("New York Knicks", "---", "nyk"),
    19: ("Orlando Magic", "---", "orl"),
    20: ("Philadelphia 76ers", "---", "phi"),
    21: ("Phoenix Suns", "---", "phx"),
    22: ("Portland Trail Blazers", "---", "por"),
    23: ("Sacramento Kings", "---", "sac"),
    24: ("San Antonio Spurs", "---", "sas"),
    25: ("Oklahoma City Thunder", "---", "okc"),
    26: ("Utah Jazz", "---", "uta"),
    27: ("Washington Wizards", "---", "was"),
    28: ("Toronto Raptors", "---", "tor"),
    29: ("Memphis Grizzlies", "---", "mem"),
    30: ("Charlotte Hornets", "---", "cha")
}


async def fetch_schedule_for_team(session: aiohttp.ClientSession, team_id: int, season_year: int) -> List[Dict]:
    """Fetch schedule for a specific team and season. Returns list of game dicts.

    Args:
        team_id: ESPN team ID (1-30)
        season_year: The second year of the season (e.g., 2024 for 2023-2024 season)
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule?season={season_year}"

    try:
        async with session.get(url) as response:
            data = await response.json()

        events = data.get("events", [])
        games = []

        for event in events:
            # Filter to regular season only
            season_type = event.get("seasonType", {})
            if season_type.get("id") != "2":  # "2" is regular season
                continue

            # Get event details
            event_id = event.get("id")
            if not event_id:
                continue

            # Get competition data
            competitions = event.get("competitions", [])
            if not competitions or len(competitions) == 0:
                continue

            competition = competitions[0]
            competitors = competition.get("competitors", [])

            if len(competitors) < 2:
                continue

            # Extract home and away teams
            home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_team or not away_team:
                continue

            try:
                # Parse game date
                game_date_str = event.get("date")
                if not game_date_str:
                    continue

                # Parse as UTC datetime
                game_datetime_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                # Convert to US Eastern time to get the correct local game date
                game_datetime_et = game_datetime_utc.astimezone(ZoneInfo("America/New_York"))
                game_date = game_datetime_et.date()

                # Get season year from event
                season = event.get("season", {}).get("year", season_year)

                games.append({
                    "game_id": event_id,
                    "date": game_date,
                    "season_year": season,
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
        print(f"Error fetching schedule for team {team_id}, season {season_year}: {e}")
        return []


async def fetch_team_game_stats(session: aiohttp.ClientSession, event_id: str, team_id: int) -> Dict[str, float]:
    """Fetch team statistics for a specific game. Returns dict of stat_name: value."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"

    # Whitelist of statistics to keep (good for similarity analysis)
    ALLOWED_STATS = {
        # Shooting efficiency
        "fieldGoalPct",
        "threePointFieldGoalPct",
        "freeThrowPct",
        # Rebounds
        "totalRebounds",
        "offensiveRebounds",
        "defensiveRebounds",
        # Playmaking
        "assists",
        "turnovers",
        # Defense
        "steals",
        "blocks",
        # Discipline
        "fouls",
        # Scoring patterns
        "fastBreakPoints",
        "pointsInPaint"
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
            stat_value = stat.get("displayValue")  # Basketball API uses displayValue

            # Only process whitelisted stats
            if stat_name in ALLOWED_STATS and stat_value is not None:
                # Try to convert to float, skip if it's a string like "-" or "N/A"
                if isinstance(stat_value, (int, float)):
                    stats_dict[stat_name] = float(stat_value)
                elif isinstance(stat_value, str) and stat_value not in ["-", "N/A", "", "--"]:
                    try:
                        stats_dict[stat_name] = float(stat_value)
                    except ValueError:
                        # Skip non-numeric values
                        pass

        return stats_dict
    except Exception as e:
        print(f"Error fetching stats for event {event_id}, team {team_id}: {e}")
        return {}


def get_team_cumulative_stats(team_id: int, season_year: int, before_date,
                              schedules_cache: Dict, stats_cache: Dict) -> Dict[str, Optional[float]]:
    """Calculate cumulative per-game stats for a team up to (not including) a specific date.

    Args:
        team_id: ESPN team ID
        season_year: The second year of the season (e.g., 2024 for 2023-2024 season)
        before_date: Calculate stats for all games before this date
        schedules_cache: Pre-fetched schedules dict {(team_id, season): [games]}
        stats_cache: Pre-fetched stats dict {(game_id, team_id): stats_dict}
    """

    # Get all games for this team from cache
    cache_key = (team_id, season_year)
    all_games = schedules_cache.get(cache_key, [])

    # Filter to games before the target date
    previous_games = [game for game in all_games if game["date"] < before_date]

    if not previous_games:
        # No previous games found, return empty stats
        return {}

    # Aggregate stats from cache
    stat_totals = {}
    games_with_stats = 0

    for game in previous_games:
        game_id = game["game_id"]
        stats_key = (game_id, team_id)

        game_stats = stats_cache.get(stats_key, {})

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


async def fetch_game_stats(session: aiohttp.ClientSession, game_info: Dict,
                           schedules_cache: Dict, stats_cache: Dict,
                           fetch_market: bool = True) -> Dict:
    """Fetch all stats for a single game including cumulative team stats and Polymarket data."""

    event_id = game_info["game_id"]
    game_date = game_info["date"]
    away_id = game_info["away_id"]
    home_id = game_info["home_id"]
    season_year = game_info["season_year"]

    try:
        # Get cumulative stats for both teams from cache
        away_stats = get_team_cumulative_stats(away_id, season_year, game_date, schedules_cache, stats_cache)
        home_stats = get_team_cumulative_stats(home_id, season_year, game_date, schedules_cache, stats_cache)

        # Build row
        row = {
            "game_id": event_id,
            "game_date": game_date,
            "season": season_year,
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
                    sport="nba",
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
                               schedules_cache: Dict, stats_cache: Dict,
                               max_concurrent: int, fetch_market_data: bool) -> List[Dict]:
    """Fetch stats for all games with concurrency control."""
    if not games:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(game):
        async with semaphore:
            return await fetch_game_stats(session, game, schedules_cache, stats_cache, fetch_market_data)

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


async def get_historical_data(start_season: int, end_season: int,
                              max_concurrent: int = 5,
                              fetch_market_data: bool = True) -> pd.DataFrame:
    """Fetch historical NBA game data with team stats and optionally market data.

    Args:
        start_season: Starting season year (e.g., 2024 for 2023-2024 season)
        end_season: Ending season year (e.g., 2025 for 2024-2025 season)
        max_concurrent: Maximum number of concurrent requests
        fetch_market_data: Whether to fetch Polymarket market data

    Returns:
        DataFrame with game data, cumulative per-game team stats, and market data.
        Excludes games from the first 2 calendar weeks of each season.
    """

    # Create session for all requests
    async with aiohttp.ClientSession() as session:
        # Collect all seasons to fetch (inclusive range)
        seasons_to_fetch = list(range(start_season, end_season + 1))

        print(f"Fetching data for seasons: {seasons_to_fetch}")

        # Fetch schedules for all teams across all seasons
        all_schedule_tasks = []
        for season in seasons_to_fetch:
            for team_id in range(1, 31):  # NBA has 30 teams (IDs 1-30)
                all_schedule_tasks.append(fetch_schedule_for_team(session, team_id, season))

        print(f"Fetching schedules for {len(all_schedule_tasks)} team-seasons...")
        all_schedules = await asyncio.gather(*all_schedule_tasks)

        # Flatten all games and remove duplicates
        all_games_dict = {}  # Use dict to deduplicate by game_id
        season_start_dates = {}  # Track first game date for each season

        for games in all_schedules:
            for game in games:
                game_id = game["game_id"]
                season = game["season_year"]

                # Track season start dates
                if season not in season_start_dates:
                    season_start_dates[season] = game["date"]
                else:
                    season_start_dates[season] = min(season_start_dates[season], game["date"])

                # Add game (deduplicates automatically)
                if game_id not in all_games_dict:
                    all_games_dict[game_id] = game

        # Filter out games from first 2 calendar weeks of each season
        filtered_games = []
        for game in all_games_dict.values():
            season = game["season_year"]
            season_start = season_start_dates.get(season)

            if season_start:
                # Calculate cutoff date (2 weeks from season start)
                cutoff_date = season_start + timedelta(days=14)

                # Only include games after the first 2 weeks
                if game["date"] >= cutoff_date:
                    filtered_games.append(game)

        print(f"Found {len(all_games_dict)} total games")
        print(f"After filtering first 2 weeks: {len(filtered_games)} games")

        if not filtered_games:
            return pd.DataFrame()

        # Build schedules cache from already-fetched schedules
        print("Building schedules cache...")
        schedules_cache = {}
        for i, games in enumerate(all_schedules):
            if games:
                # Determine team_id and season from first game in schedule
                first_game = games[0]
                season = first_game["season_year"]

                # Determine which team this schedule belongs to
                # Since we fetched in order (team_id 1-30), we can calculate
                team_id = (i % 30) + 1  # Team IDs are 1-30

                cache_key = (team_id, season)
                schedules_cache[cache_key] = games

        print(f"Schedules cache built: {len(schedules_cache)} team-seasons")

        # Build stats cache by pre-fetching all game stats
        print("Pre-fetching game stats for all unique games...")

        # Collect all unique (game_id, team_id) pairs needed
        games_to_fetch = set()
        for game in all_games_dict.values():
            game_id = game["game_id"]
            away_id = game["away_id"]
            home_id = game["home_id"]
            games_to_fetch.add((game_id, away_id))
            games_to_fetch.add((game_id, home_id))

        print(f"Fetching stats for {len(games_to_fetch)} game-team combinations...")

        # Batch fetch all game stats with concurrency control
        stats_semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_stat_with_limit(game_id, team_id):
            async with stats_semaphore:
                stats = await fetch_team_game_stats(session, game_id, team_id)
                return ((game_id, team_id), stats)

        stat_tasks = [fetch_stat_with_limit(gid, tid) for gid, tid in games_to_fetch]
        stat_results = await tqdm_asyncio.gather(*stat_tasks, desc="Fetching stats")

        # Build stats cache
        stats_cache = {}
        for key, stats in stat_results:
            if stats:  # Only cache non-empty stats
                stats_cache[key] = stats

        print(f"Stats cache built: {len(stats_cache)} entries")

        # Fetch stats for all games using caches
        rows = await fetch_all_game_stats(session, filtered_games, schedules_cache, stats_cache,
                                         max_concurrent, fetch_market_data)

    # Return as DataFrame
    return pd.DataFrame(rows).dropna()


def get_historical_data_sync(start_season: int, end_season: int,
                             fetch_market_data: bool = True) -> pd.DataFrame:
    """Synchronous wrapper for the async function.

    Args:
        start_season: Starting season year (e.g., 2024 for 2023-2024 season)
        end_season: Ending season year (e.g., 2025 for 2024-2025 season)
        fetch_market_data: Whether to fetch Polymarket market data
    """
    return asyncio.run(get_historical_data(start_season, end_season,
                                          fetch_market_data=fetch_market_data))


if __name__ == "__main__":
    import time

    # Test with 2024 season (2023-2024)
    start_season = 2024
    end_season = 2024

    print(f"Fetching games from {start_season-1}-{start_season} to {end_season-1}-{end_season} season...")
    start_time = time.time()

    df = get_historical_data_sync(start_season, end_season, fetch_market_data=True)

    elapsed = time.time() - start_time
    print(f"\nFetched {len(df)} games in {elapsed:.2f} seconds")
    print(f"\nColumns: {df.columns.tolist()}")
    if len(df) > 0:
        print(f"\nFirst game:\n{df.iloc[0]}")
        print(f"\nSample stats:")
        print(df[["game_id", "game_date", "away_team", "home_team",
                  "away_fieldGoalPct", "home_fieldGoalPct"]].head())
