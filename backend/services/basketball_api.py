"""Fetch cumulative NBA team stats prior to game dates."""
from __future__ import annotations
import asyncio
import time
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Union

import aiohttp
import pandas as pd
import requests
from nba_api.stats.endpoints import teamgamelog, scoreboardv2
from nba_api.stats.static import teams as teams_static
import polymarket_api as polyapi
RATE_LIMIT_SECONDS = 0.6
REQUEST_TIMEOUT = 30

# Cache team information for fast lookups
_TEAM_INFO_CACHE = {}

def _get_team_info(team_id: int) -> dict:
    """Get team info from cache or fetch if not cached."""
    if not _TEAM_INFO_CACHE:
        # Populate cache on first call
        all_teams = teams_static.get_teams()
        for team in all_teams:
            _TEAM_INFO_CACHE[team['id']] = team
    return _TEAM_INFO_CACHE.get(team_id, {})
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5.0

_last_call_ts = 0.0
_rate_lock = asyncio.Lock()
_gamelog_cache: Dict[tuple, pd.DataFrame] = {}  # Cache for (team_id, season, season_type) -> full game log

PER_GAME_COLUMNS = [
    "MIN", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS",
]

PERCENT_DEPENDENCIES = {
    "FG_PCT": ("FGM", "FGA"),
    "FG3_PCT": ("FG3M", "FG3A"),
    "FT_PCT": ("FTM", "FTA"),
}

_TEAMS: Dict[str, Dict[str, Union[str, int]]] = {
    str(team["id"]): team for team in teams_static.get_teams()
}


async def _rate_limit() -> None:
    """Enforce rate limiting between API calls."""
    global _last_call_ts
    async with _rate_lock:
        now = time.monotonic()
        wait = RATE_LIMIT_SECONDS - (now - _last_call_ts)
        if wait > 0:
            await asyncio.sleep(wait)
            now = time.monotonic()
        _last_call_ts = now


def _as_datetime(value: Union[date, datetime, str]) -> datetime:
    """Convert various date formats to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return pd.to_datetime(value).to_pydatetime()


def _season_from_date(game_day: date) -> str:
    """Determine NBA season string from a date (e.g., '2024-25')."""
    if game_day.month >= 8:
        start_year = game_day.year
        end_year = (game_day.year + 1) % 100
    else:
        start_year = game_day.year - 1
        end_year = game_day.year % 100
    return f"{start_year}-{str(end_year).zfill(2)}"


async def _fetch_full_season_gamelog(
    team_id: int,
    season: str,
    season_type: str,
) -> pd.DataFrame:
    """Fetch full season game log for a team (cached)."""
    cache_key = (team_id, season, season_type)

    # Check cache first
    if cache_key in _gamelog_cache:
        return _gamelog_cache[cache_key]

    # Fetch full season (no date_to filter)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await asyncio.to_thread(
                teamgamelog.TeamGameLog,
                team_id=str(team_id),
                season=season,
                season_type_all_star=season_type,
                league_id_nullable="00",
                timeout=REQUEST_TIMEOUT,
            )
            df = response.get_data_frames()[0]
            if "GAME_DATE" not in df.columns:
                raise RuntimeError("TeamGameLog response missing GAME_DATE column")
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], format='mixed')
            await _rate_limit()

            # Cache the result
            _gamelog_cache[cache_key] = df
            return df
        except Exception as err:
            fail_fast = isinstance(err, requests.exceptions.ConnectionError)
            if fail_fast or attempt >= MAX_ATTEMPTS:
                raise
            sleep_for = min(RETRY_BACKOFF_SECONDS * attempt, 6.0)
            print(f"Retrying TeamGameLog for team {team_id} (attempt {attempt}): {err}")
            await asyncio.sleep(sleep_for)

    # Should never reach here due to raise in loop, but satisfies type checker
    raise RuntimeError(f"Failed to fetch team gamelog for team {team_id}")


async def _fetch_team_gamelog(
    team_id: int,
    season: str,
    season_type: str,
    through_date: datetime,
) -> pd.DataFrame:
    """Fetch team game log up to (but not including) through_date (uses cache)."""
    # Get full season from cache
    full_log = await _fetch_full_season_gamelog(team_id, season, season_type)

    # Filter to games before through_date
    if full_log.empty:
        return full_log

    filtered = full_log[full_log["GAME_DATE"] < through_date].copy()
    return filtered


async def _fetch_scoreboard(game_day: date) -> pd.DataFrame:
    """Fetch NBA scoreboard for a specific date."""
    nba_date = game_day.strftime("%m/%d/%Y")
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            board = await asyncio.to_thread(
                scoreboardv2.ScoreboardV2,
                game_date=nba_date,
                league_id="00",
                timeout=REQUEST_TIMEOUT,
            )
            df = board.game_header.get_data_frame()
            await _rate_limit()
            return df
        except Exception as err:
            fail_fast = isinstance(err, requests.exceptions.ConnectionError)
            if fail_fast or attempt >= MAX_ATTEMPTS:
                raise
            sleep_for = min(RETRY_BACKOFF_SECONDS * attempt, 6.0)
            print(f"Retrying Scoreboard for {nba_date} (attempt {attempt}): {err}")
            await asyncio.sleep(sleep_for)
    
    # Should never reach here due to raise in loop, but satisfies type checker
    raise RuntimeError(f"Failed to fetch scoreboard for {nba_date}")


async def _get_team_cumulative_stats(
    team_id: int,
    game_date: datetime,
    season: str,
    season_type: str,
) -> Dict[str, float]:
    """Get cumulative stats for a team up to (not including) game_date."""
    log_df = await _fetch_team_gamelog(team_id, season, season_type, game_date)
    
    if log_df is None or log_df.empty:
        # Return zeros if no data available
        stats = {f"AVG_{col}": 0.0 for col in PER_GAME_COLUMNS}
        stats.update({pct_col: 0.0 for pct_col in PERCENT_DEPENDENCIES})
        return stats
    
    games_played = len(log_df)
    stats = {}
    totals = {}

    for col in PER_GAME_COLUMNS:
        if col in log_df.columns:
            series = pd.to_numeric(log_df[col], errors="coerce")
            total = float(series.sum(skipna=True))
            totals[col] = total
            stats[f"AVG_{col}"] = total / games_played if games_played else 0.0
        else:
            stats[f"AVG_{col}"] = 0.0
    
    for pct_col, (made_col, att_col) in PERCENT_DEPENDENCIES.items():
        made = totals.get(made_col)
        attempts = totals.get(att_col)
        stats[pct_col] = made / attempts if made and attempts and attempts > 0 else 0.0

    return stats


async def get_matchups_cumulative_stats_between(
    start_date: Union[date, datetime, str],
    end_date: Union[date, datetime, str],
    *,
    season_type: str = "Regular Season",
    max_concurrency: int = 2,
) -> pd.DataFrame:
    """
    Get cumulative stats for all NBA games between two dates.
    
    Returns one row per game with HOME_ and AWAY_ prefixed columns showing
    each team's cumulative stats leading up to (but not including) that game.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        season_type: NBA season type (default "Regular Season")
        max_concurrency: Max concurrent API calls
        
    Returns:
        DataFrame with columns:
            GAME_ID, GAME_DATE, HOME_TEAM_ID, AWAY_TEAM_ID,
            HOME_AVG_PTS, HOME_AVG_REB, ..., HOME_FG_PCT,
            AWAY_AVG_PTS, AWAY_AVG_REB, ..., AWAY_FG_PCT
    """
    start_day = _as_datetime(start_date).date()
    end_day = _as_datetime(end_date).date()

    if end_day < start_day:
        raise ValueError("end_date must be on or after start_date")

    # Create session for Polymarket API calls
    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(max(1, max_concurrency))

        # Pre-fetch all scoreboards in parallel (with rate limiting)
        date_list = [start_day + timedelta(days=i) for i in range((end_day - start_day).days + 1)]

        # Limit concurrent scoreboard fetches to prevent API overwhelming
        async def _fetch_scoreboard_limited(date_val):
            async with scoreboard_semaphore:
                return await _fetch_scoreboard(date_val)

        scoreboard_semaphore = asyncio.Semaphore(10)  # Max 10 concurrent scoreboard requests
        scoreboard_tasks = [_fetch_scoreboard_limited(d) for d in date_list]
        scoreboard_results = await asyncio.gather(*scoreboard_tasks, return_exceptions=True)

        # Build date->scoreboard mapping
        scoreboards = {}
        for date_val, result in zip(date_list, scoreboard_results):
            if isinstance(result, Exception):
                print(f"Skipping {date_val.isoformat()}: scoreboard error: {result}")
                continue
            if not result.empty:
                scoreboards[date_val] = result

        # Process all games
        tasks = []
        for current, board_df in scoreboards.items():
            for _, row in board_df.iterrows():
                game_id = row["GAME_ID"]
                home_id = int(row["HOME_TEAM_ID"])
                away_id = int(row["VISITOR_TEAM_ID"])

                if str(home_id) not in _TEAMS or str(away_id) not in _TEAMS:
                    continue
                async def _collect_game(
                    game_id=game_id,
                    game_date=current,
                    home_id=home_id,
                    away_id=away_id,
                ):
                    async with semaphore:
                        season = _season_from_date(game_date)
                        away_team_slug = str(_TEAMS[str(away_id)]["abbreviation"]).lower()
                        home_team_slug = str(_TEAMS[str(home_id)]["abbreviation"]).lower()
                        # 1) Fetch NBA stats concurrently
                        home_stats, away_stats = await asyncio.gather(
                            _get_team_cumulative_stats(
                                home_id, _as_datetime(game_date), season, season_type
                            ),
                            _get_team_cumulative_stats(
                                away_id, _as_datetime(game_date), season, season_type
                            ),
                        )
                        # 2) Best-effort Polymarket call
                        slug = f"nba-{away_team_slug}-{home_team_slug}-{game_date:%Y-%m-%d}"
                        try:
                            opening = await polyapi.get_opening_price(
                                session,  # Pass session as first argument
                                sport="nba",
                                date=game_date,
                                away_team=away_team_slug,
                                home_team=home_team_slug,
                            )
                        except Exception as e:
                            print(f"Polymarket error for slug {slug}: {e}")
                            opening = None

                        # Get team names
                        home_team_info = _get_team_info(home_id)
                        away_team_info = _get_team_info(away_id)

                        row_data = {
                            "game_id": game_id,
                            "game_date": pd.Timestamp(game_date),
                            "home_team_id": home_id,
                            "away_team_id": away_id,
                            "home_team": home_team_info.get('full_name', 'Unknown'),
                            "away_team": away_team_info.get('full_name', 'Unknown'),
                        }
                        # cumulative stats (lowercase)
                        for key, value in home_stats.items():
                            row_data[f"home_{key}"] = value
                        for key, value in away_stats.items():
                            row_data[f"away_{key}"] = value
                        # opening prices + timestamps (new columns)
                        if opening is not None:
                            row_data["polymarket_away_price"] = opening["away_price"]
                            row_data["polymarket_home_price"] = opening["home_price"]
                            row_data["polymarket_start_ts"] = opening["start_ts"]
                            row_data["polymarket_market_open_ts"] = opening["market_open_ts"]
                            row_data["polymarket_market_close_ts"] = opening.get("market_close_ts")
                        else:
                            row_data["polymarket_away_price"] = None
                            row_data["polymarket_home_price"] = None
                            row_data["polymarket_start_ts"] = None
                            row_data["polymarket_market_open_ts"] = None
                            row_data["polymarket_market_close_ts"] = None
                        return row_data
                tasks.append(asyncio.create_task(_collect_game()))

        if not tasks:
            return pd.DataFrame()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        rows = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Game collection error: {result}")
                continue
            rows.append(result)

        return pd.DataFrame(rows) if rows else pd.DataFrame()


__all__ = ["get_matchups_cumulative_stats_between"]