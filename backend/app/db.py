from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Date,
    DateTime
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
from pathlib import Path
import pandas as pd

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NBAGameFeatures(Base):
    __tablename__ = "nba_games_features"

    game_id = Column(String, primary_key=True, nullable=False)

    sport = Column(String, nullable=False)
    season = Column(Integer, nullable=True)
    game_date = Column(Date)

    home_team_id = Column(Integer, nullable=False)
    away_team_id = Column(Integer, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)

    # Away Team Cumulative Stats (ESPN)
    away_fieldGoalPct = Column(Float)
    away_threePointFieldGoalPct = Column(Float)
    away_freeThrowPct = Column(Float)
    away_totalRebounds = Column(Float)
    away_offensiveRebounds = Column(Float)
    away_defensiveRebounds = Column(Float)
    away_assists = Column(Float)
    away_turnovers = Column(Float)
    away_steals = Column(Float)
    away_blocks = Column(Float)
    away_fouls = Column(Float)
    away_fastBreakPoints = Column(Float)
    away_pointsInPaint = Column(Float)

    # Home Team Cumulative Stats (ESPN)
    home_fieldGoalPct = Column(Float)
    home_threePointFieldGoalPct = Column(Float)
    home_freeThrowPct = Column(Float)
    home_totalRebounds = Column(Float)
    home_offensiveRebounds = Column(Float)
    home_defensiveRebounds = Column(Float)
    home_assists = Column(Float)
    home_turnovers = Column(Float)
    home_steals = Column(Float)
    home_blocks = Column(Float)
    home_fouls = Column(Float)
    home_fastBreakPoints = Column(Float)
    home_pointsInPaint = Column(Float)

    # Polymarket Data
    polymarket_home_price = Column(Float)
    polymarket_away_price = Column(Float)
    polymarket_start_ts = Column(Integer)
    polymarket_market_open_ts = Column(Integer)
    polymarket_market_close_ts = Column(Integer)


def prepare_nba_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform basketball_api DataFrame to match NBAGameFeatures schema.

    Transformations:
    - Add 'sport' column with value 'NBA'
    - Add 'season' column (start year of NBA season)
    - Unix timestamps are stored as-is (integers)

    Args:
        df: DataFrame from basketball_api.get_matchups_cumulative_stats_between()

    Returns:
        Transformed DataFrame ready for database insertion
    """
    df_copy = df.copy()

    # Add sport column
    df_copy['sport'] = 'NBA'

    # Add season column (start year of NBA season as integer)
    # NBA season spans two years: Oct-June (e.g., 2024-25 season starts Oct 2024)
    # If month >= 10 (Oct-Dec), season is current year
    # If month < 10 (Jan-Sep), season is previous year
    df_copy['season'] = df_copy['game_date'].apply(
        lambda d: d.year if d.month >= 10 else d.year - 1
    )

    # Unix timestamps are stored as-is (no conversion needed)

    return df_copy


def insert_nba_games(df: pd.DataFrame) -> int:
    """
    Insert NBA games DataFrame into database.
    Automatically filters out games that already exist (by game_id).

    Args:
        df: DataFrame from basketball_api.get_matchups_cumulative_stats_between()

    Returns:
        Number of new rows inserted (excludes duplicates)

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_nba_df_for_db(df)

    session = SessionLocal()
    try:
        # Query existing game_ids to filter out duplicates
        existing_ids = session.query(NBAGameFeatures.game_id).all()
        existing_ids_set = {g[0] for g in existing_ids}

        # Filter out games that already exist
        df_new = df_prepared[~df_prepared['game_id'].isin(existing_ids_set)]

        duplicates_count = len(df_prepared) - len(df_new)
        if duplicates_count > 0:
            print(f"  Skipping {duplicates_count} games that already exist in database")

        if len(df_new) == 0:
            print("  No new games to insert")
            return 0

        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_new.to_sql(
            'nba_games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_new)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def prepare_nfl_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform football_api DataFrame to match NFLGameFeatures schema.

    Transformations:
    - Add 'sport' column with value 'NFL'
    - Add 'season' column (extracted from year)
    - Unix timestamps are stored as-is (integers)

    Args:
        df: DataFrame from football_api.get_historical_data_sync()

    Returns:
        Transformed DataFrame ready for database insertion
    """
    df_copy = df.copy()

    # Add sport column
    df_copy['sport'] = 'NFL'

    # Add season column (same as year for NFL)
    df_copy['season'] = df_copy['year']

    # Unix timestamps are stored as-is (no conversion needed)

    return df_copy


def insert_nfl_games(df: pd.DataFrame) -> int:
    """
    Insert NFL games DataFrame into database.
    Automatically filters out games that already exist (by game_id).

    Args:
        df: DataFrame from football_api.get_historical_data_sync()

    Returns:
        Number of new rows inserted (excludes duplicates)

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_nfl_df_for_db(df)

    session = SessionLocal()
    try:
        # Query existing game_ids to filter out duplicates
        existing_ids = session.query(NFLGameFeatures.game_id).all()
        existing_ids_set = {g[0] for g in existing_ids}

        # Filter out games that already exist
        df_new = df_prepared[~df_prepared['game_id'].isin(existing_ids_set)]

        duplicates_count = len(df_prepared) - len(df_new)
        if duplicates_count > 0:
            print(f"  Skipping {duplicates_count} games that already exist in database")

        if len(df_new) == 0:
            print("  No new games to insert")
            return 0

        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_new.to_sql(
            'nfl_games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_new)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


class NFLGameFeatures(Base):
    __tablename__ = "nfl_games_features"

    game_id = Column(String, primary_key=True, nullable=False)

    sport = Column(String, nullable=False)  # 'NFL'
    season = Column(Integer, nullable=True)  # Year (e.g., 2024)
    game_date = Column(Date, nullable=False)
    week = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    home_team = Column(String, nullable=False)
    home_team_id = Column(Integer, nullable=False)
    away_team = Column(String, nullable=False)
    away_team_id = Column(Integer, nullable=False)

    # Away Team Cumulative Stats (efficiency metrics)
    away_thirdDownEff = Column(Float)
    away_fourthDownEff = Column(Float)
    away_yardsPerPlay = Column(Float)
    away_yardsPerPass = Column(Float)
    away_yardsPerRushAttempt = Column(Float)
    away_redZoneAttempts = Column(Float)

    # Away Team Volume Metrics
    away_firstDowns = Column(Float)
    away_netPassingYards = Column(Float)
    away_rushingYards = Column(Float)
    away_interceptions = Column(Float)
    away_fumblesLost = Column(Float)

    # Home Team Cumulative Stats (efficiency metrics)
    home_thirdDownEff = Column(Float)
    home_fourthDownEff = Column(Float)
    home_yardsPerPlay = Column(Float)
    home_yardsPerPass = Column(Float)
    home_yardsPerRushAttempt = Column(Float)
    home_redZoneAttempts = Column(Float)

    # Home Team Volume Metrics
    home_firstDowns = Column(Float)
    home_netPassingYards = Column(Float)
    home_rushingYards = Column(Float)
    home_interceptions = Column(Float)
    home_fumblesLost = Column(Float)

    # Polymarket Data
    polymarket_away_price = Column(Float)
    polymarket_home_price = Column(Float)
    polymarket_start_ts = Column(Integer)
    polymarket_market_open_ts = Column(Integer)
    polymarket_market_close_ts = Column(Integer)


def prepare_mlb_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform baseball_api DataFrame to match MLBGameFeatures schema.

    Transformations:
    - Add 'sport' column with value 'MLB'
    - Add 'season' column (year from game_date)
    - Convert game_id to string if needed
    - Unix timestamps are stored as-is (integers)

    Args:
        df: DataFrame from baseball_api.get_historical_data_sync()

    Returns:
        Transformed DataFrame ready for database insertion
    """
    df_copy = df.copy()

    # Add sport column
    df_copy['sport'] = 'MLB'

    # Add season column (extract year from game_date)
    df_copy['season'] = df_copy['game_date'].apply(lambda d: d.year)

    # Convert game_id to string (MLB API returns int)
    df_copy['game_id'] = df_copy['game_id'].astype(str)

    # Unix timestamps are stored as-is (no conversion needed)

    return df_copy


def insert_mlb_games(df: pd.DataFrame) -> int:
    """
    Insert MLB games DataFrame into database.
    Automatically filters out games that already exist (by game_id).

    Args:
        df: DataFrame from baseball_api.get_historical_data_sync()

    Returns:
        Number of new rows inserted (excludes duplicates)

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_mlb_df_for_db(df)

    session = SessionLocal()
    try:
        # Query existing game_ids to filter out duplicates
        existing_ids = session.query(MLBGameFeatures.game_id).all()
        existing_ids_set = {g[0] for g in existing_ids}

        # Filter out games that already exist
        df_new = df_prepared[~df_prepared['game_id'].isin(existing_ids_set)]

        duplicates_count = len(df_prepared) - len(df_new)
        if duplicates_count > 0:
            print(f"  Skipping {duplicates_count} games that already exist in database")

        if len(df_new) == 0:
            print("  No new games to insert")
            return 0

        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_new.to_sql(
            'mlb_games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_new)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


class MLBGameFeatures(Base):
    __tablename__ = "mlb_games_features"

    game_id = Column(String, primary_key=True, nullable=False)

    sport = Column(String, nullable=False)  # 'MLB'
    season = Column(Integer, nullable=True)  # Year (e.g., 2024)
    game_date = Column(Date, nullable=False)

    home_team = Column(String, nullable=False)
    home_team_id = Column(Integer, nullable=False)
    away_team = Column(String, nullable=False)
    away_team_id = Column(Integer, nullable=False)

    # Away Team Hitting Stats
    away_hitting_avg = Column(Float)
    away_hitting_obp = Column(Float)
    away_hitting_slg = Column(Float)
    away_hitting_ops = Column(Float)
    away_hitting_stolenBasePercentage = Column(Float)
    away_hitting_babip = Column(Float)
    away_hitting_groundOutsToAirouts = Column(Float)
    away_hitting_atBatsPerHomeRun = Column(Float)

    # Away Team Pitching Stats
    away_pitching_avg = Column(Float)
    away_pitching_obp = Column(Float)
    away_pitching_slg = Column(Float)
    away_pitching_ops = Column(Float)
    away_pitching_stolenBasePercentage = Column(Float)
    away_pitching_era = Column(Float)
    away_pitching_whip = Column(Float)
    away_pitching_groundOutsToAirouts = Column(Float)
    away_pitching_pitchesPerInning = Column(Float)
    away_pitching_strikeoutsPer9Inn = Column(Float)
    away_pitching_walksPer9Inn = Column(Float)
    away_pitching_hitsPer9Inn = Column(Float)
    away_pitching_runsScoredPer9 = Column(Float)
    away_pitching_homeRunsPer9 = Column(Float)

    # Home Team Hitting Stats
    home_hitting_avg = Column(Float)
    home_hitting_obp = Column(Float)
    home_hitting_slg = Column(Float)
    home_hitting_ops = Column(Float)
    home_hitting_stolenBasePercentage = Column(Float)
    home_hitting_babip = Column(Float)
    home_hitting_groundOutsToAirouts = Column(Float)
    home_hitting_atBatsPerHomeRun = Column(Float)

    # Home Team Pitching Stats
    home_pitching_avg = Column(Float)
    home_pitching_obp = Column(Float)
    home_pitching_slg = Column(Float)
    home_pitching_ops = Column(Float)
    home_pitching_stolenBasePercentage = Column(Float)
    home_pitching_era = Column(Float)
    home_pitching_whip = Column(Float)
    home_pitching_groundOutsToAirouts = Column(Float)
    home_pitching_pitchesPerInning = Column(Float)
    home_pitching_strikeoutsPer9Inn = Column(Float)
    home_pitching_walksPer9Inn = Column(Float)
    home_pitching_hitsPer9Inn = Column(Float)
    home_pitching_runsScoredPer9 = Column(Float)
    home_pitching_homeRunsPer9 = Column(Float)

    # Polymarket Data
    polymarket_away_price = Column(Float)
    polymarket_home_price = Column(Float)
    polymarket_start_ts = Column(Integer)
    polymarket_market_open_ts = Column(Integer)
    polymarket_market_close_ts = Column(Integer)


class ActiveMarket(Base):
    """
    Tracks which game markets are currently active and being monitored for price updates.

    A market is considered active from when it's discovered until the game starts or the
    market is closed/resolved.
    """
    __tablename__ = "active_markets"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Market identification
    market_id = Column(String, nullable=False, unique=True)  # Polymarket market ID
    polymarket_slug = Column(String, nullable=False)  # URL slug format: "nfl-giants-broncos-2024-11-08"

    # Game information
    sport = Column(String, nullable=False)  # 'NBA' or 'NFL'
    game_date = Column(Date, nullable=False)
    away_team = Column(String, nullable=False)
    away_team_id = Column(String, nullable=True)
    home_team = Column(String, nullable=False)
    home_team_id = Column(String, nullable=True)

    # Timing (Unix timestamps)
    game_start_ts = Column(Integer, nullable=False)  # When the game starts
    market_open_ts = Column(Integer, nullable=True)  # When market opened for trading
    market_close_ts = Column(Integer, nullable=True)  # When market closed

    # Status tracking
    market_status = Column(String, nullable=False, default='open')  # 'open', 'closed', 'resolved'
    last_updated = Column(Integer, nullable=False)  # Last time we fetched a price for this market (Unix timestamp)

    # Metadata
    created_at = Column(DateTime, nullable=False)  # When we first discovered this market


def insert_active_markets(markets: list[dict]) -> int:
    """
    Insert newly discovered active markets into the database.

    Args:
        markets: List of market dicts with keys:
            - market_id (str)
            - polymarket_slug (str)
            - sport (str): 'NBA' or 'NFL'
            - game_date (date)
            - away_team (str)
            - away_team_id (str, optional)
            - home_team (str)
            - home_team_id (str, optional)
            - game_start_ts (int): Unix timestamp
            - market_open_ts (int, optional): Unix timestamp
            - market_close_ts (int, optional): Unix timestamp
            - market_status (str): default 'open'

    Returns:
        Number of markets inserted (ignores duplicates)
    """
    from datetime import datetime

    session = SessionLocal()
    inserted_count = 0

    try:
        for market_data in markets:
            # Check if market already exists
            existing = session.query(ActiveMarket).filter_by(
                market_id=market_data['market_id']
            ).first()

            if not existing:
                now_datetime = datetime.utcnow()
                now_timestamp = int(now_datetime.timestamp())

                # Helper to ensure timestamps are integers
                def to_unix_timestamp(val):
                    if val is None:
                        return None
                    if isinstance(val, datetime):
                        return int(val.timestamp())
                    return int(val)

                market = ActiveMarket(
                    market_id=market_data['market_id'],
                    polymarket_slug=market_data['polymarket_slug'],
                    sport=market_data['sport'],
                    game_date=market_data['game_date'],
                    away_team=market_data['away_team'],
                    away_team_id=market_data.get('away_team_id'),
                    home_team=market_data['home_team'],
                    home_team_id=market_data.get('home_team_id'),
                    game_start_ts=to_unix_timestamp(market_data['game_start_ts']),
                    market_open_ts=to_unix_timestamp(market_data.get('market_open_ts')),
                    market_close_ts=to_unix_timestamp(market_data.get('market_close_ts')),
                    market_status=market_data.get('market_status', 'open'),
                    last_updated=now_timestamp,
                    created_at=now_datetime
                )
                session.add(market)
                inserted_count += 1

        session.commit()
        return inserted_count
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_active_markets(status: str = 'open') -> list[dict]:
    """
    Retrieve list of active markets to track.

    Args:
        status: Filter by market status ('open', 'closed', 'resolved'). Default 'open'.

    Returns:
        List of market dicts with all fields from ActiveMarket table.
        Note: game_start_ts, market_open_ts, market_close_ts, and last_updated are Unix timestamps (int).
        created_at is a datetime object.
    """
    session = SessionLocal()

    try:
        query = session.query(ActiveMarket)
        if status:
            query = query.filter_by(market_status=status)

        markets = query.all()

        return [
            {
                'id': m.id,
                'market_id': m.market_id,
                'polymarket_slug': m.polymarket_slug,
                'sport': m.sport,
                'game_date': m.game_date,
                'away_team': m.away_team,
                'away_team_id': m.away_team_id,
                'home_team': m.home_team,
                'home_team_id': m.home_team_id,
                'game_start_ts': m.game_start_ts,
                'market_open_ts': m.market_open_ts,
                'market_close_ts': m.market_close_ts,
                'market_status': m.market_status,
                'last_updated': m.last_updated,
                'created_at': m.created_at
            }
            for m in markets
        ]
    finally:
        session.close()
