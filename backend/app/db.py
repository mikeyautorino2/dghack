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
    __tablename__ = "games_features"

    game_id = Column(String, primary_key=True, nullable=False)

    sport = Column(String, nullable=False)
    season = Column(Integer, nullable=True)
    game_date = Column(Date)

    home_team_id = Column(Integer, nullable=False)
    away_team_id = Column(Integer, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)

    home_avg_min = Column(Float)
    home_avg_fgm = Column(Float)
    home_avg_fga = Column(Float)
    home_avg_fg3m = Column(Float)
    home_avg_fg3a = Column(Float)
    home_avg_ftm = Column(Float)
    home_avg_fta = Column(Float)
    home_avg_oreb = Column(Float)
    home_avg_dreb = Column(Float)
    home_avg_reb = Column(Float)
    home_avg_ast = Column(Float)
    home_avg_stl = Column(Float)
    home_avg_blk = Column(Float)
    home_avg_tov = Column(Float)
    home_avg_pf = Column(Float)
    home_avg_pts = Column(Float)
    home_fg_pct = Column(Float)
    home_fg3_pct = Column(Float)
    home_ft_pct = Column(Float)

    # Away
    away_avg_min = Column(Float)
    away_avg_fgm = Column(Float)
    away_avg_fga = Column(Float)
    away_avg_fg3m = Column(Float)
    away_avg_fg3a = Column(Float)
    away_avg_ftm = Column(Float)
    away_avg_fta = Column(Float)
    away_avg_oreb = Column(Float)
    away_avg_dreb = Column(Float)
    away_avg_reb = Column(Float)
    away_avg_ast = Column(Float)
    away_avg_stl = Column(Float)
    away_avg_blk = Column(Float)
    away_avg_tov = Column(Float)
    away_avg_pf = Column(Float)
    away_avg_pts = Column(Float)
    away_fg_pct = Column(Float)
    away_fg3_pct = Column(Float)
    away_ft_pct = Column(Float)

    # Polymarket Data
    polymarket_home_price = Column(Float)
    polymarket_away_price = Column(Float)
    polymarket_start_ts = Column(DateTime)
    polymarket_market_open_ts = Column(DateTime)
    polymarket_market_close_ts = Column(DateTime)


def prepare_nba_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform basketball_api DataFrame to match NBAGameFeatures schema.

    Transformations:
    - Add 'sport' column with value 'NBA'
    - Add 'season' column (start year of NBA season)
    - Convert Unix timestamps to DateTime objects (polymarket_start_ts,
      polymarket_market_open_ts, polymarket_market_close_ts)

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

    # Convert Unix timestamps to datetime (handle None/NaN values)
    if 'polymarket_start_ts' in df_copy.columns:
        df_copy['polymarket_start_ts'] = pd.to_datetime(
            df_copy['polymarket_start_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_open_ts' in df_copy.columns:
        df_copy['polymarket_market_open_ts'] = pd.to_datetime(
            df_copy['polymarket_market_open_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_close_ts' in df_copy.columns:
        df_copy['polymarket_market_close_ts'] = pd.to_datetime(
            df_copy['polymarket_market_close_ts'],
            unit='s',
            errors='coerce'
        )

    return df_copy


def insert_nba_games(df: pd.DataFrame) -> int:
    """
    Insert NBA games DataFrame into database.

    Args:
        df: DataFrame from basketball_api.get_matchups_cumulative_stats_between()

    Returns:
        Number of rows inserted

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_nba_df_for_db(df)

    session = SessionLocal()
    try:
        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_prepared.to_sql(
            'games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_prepared)
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
    - Convert Unix timestamps to DateTime objects (polymarket_start_ts,
      polymarket_market_open_ts, polymarket_market_close_ts)

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

    # Convert Unix timestamps to datetime (handle None/NaN values)
    if 'polymarket_start_ts' in df_copy.columns:
        df_copy['polymarket_start_ts'] = pd.to_datetime(
            df_copy['polymarket_start_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_open_ts' in df_copy.columns:
        df_copy['polymarket_market_open_ts'] = pd.to_datetime(
            df_copy['polymarket_market_open_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_close_ts' in df_copy.columns:
        df_copy['polymarket_market_close_ts'] = pd.to_datetime(
            df_copy['polymarket_market_close_ts'],
            unit='s',
            errors='coerce'
        )

    return df_copy


def insert_nfl_games(df: pd.DataFrame) -> int:
    """
    Insert NFL games DataFrame into database.

    Args:
        df: DataFrame from football_api.get_historical_data_sync()

    Returns:
        Number of rows inserted

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_nfl_df_for_db(df)

    session = SessionLocal()
    try:
        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_prepared.to_sql(
            'nfl_games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_prepared)
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
    polymarket_start_ts = Column(DateTime)
    polymarket_market_open_ts = Column(DateTime)
    polymarket_market_close_ts = Column(DateTime)


def prepare_mlb_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform baseball_api DataFrame to match MLBGameFeatures schema.

    Transformations:
    - Add 'sport' column with value 'MLB'
    - Add 'season' column (year from game_date)
    - Convert Unix timestamps to DateTime objects (polymarket_start_ts,
      polymarket_market_open_ts, polymarket_market_close_ts)
    - Convert game_id to string if needed

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

    # Convert Unix timestamps to datetime (handle None/NaN values)
    if 'polymarket_start_ts' in df_copy.columns:
        df_copy['polymarket_start_ts'] = pd.to_datetime(
            df_copy['polymarket_start_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_open_ts' in df_copy.columns:
        df_copy['polymarket_market_open_ts'] = pd.to_datetime(
            df_copy['polymarket_market_open_ts'],
            unit='s',
            errors='coerce'
        )
    if 'polymarket_market_close_ts' in df_copy.columns:
        df_copy['polymarket_market_close_ts'] = pd.to_datetime(
            df_copy['polymarket_market_close_ts'],
            unit='s',
            errors='coerce'
        )

    return df_copy


def insert_mlb_games(df: pd.DataFrame) -> int:
    """
    Insert MLB games DataFrame into database.

    Args:
        df: DataFrame from baseball_api.get_historical_data_sync()

    Returns:
        Number of rows inserted

    Raises:
        Exception: If insertion fails
    """
    df_prepared = prepare_mlb_df_for_db(df)

    session = SessionLocal()
    try:
        # Use pandas to_sql for efficient bulk insert
        rows_inserted = df_prepared.to_sql(
            'mlb_games_features',
            engine,
            if_exists='append',
            index=False,
            method='multi'  # Use multi-row INSERT for better performance
        )
        session.commit()
        return rows_inserted if rows_inserted else len(df_prepared)
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
    polymarket_start_ts = Column(DateTime)
    polymarket_market_open_ts = Column(DateTime)
    polymarket_market_close_ts = Column(DateTime)


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

    # Timing
    game_start_ts = Column(DateTime, nullable=False)  # When the game starts
    market_open_ts = Column(DateTime, nullable=True)  # When market opened for trading
    market_close_ts = Column(DateTime, nullable=True)  # When market closed

    # Status tracking
    market_status = Column(String, nullable=False, default='open')  # 'open', 'closed', 'resolved'
    last_updated = Column(DateTime, nullable=False)  # Last time we fetched a price for this market

    # Metadata
    created_at = Column(DateTime, nullable=False)  # When we first discovered this market


class MarketPriceHistory(Base):
    """
    Time series of price observations for active markets.

    Stores snapshots of market prices at regular intervals (every 5 minutes) for all
    active markets. Used to generate candlestick charts and analyze price movements.
    """
    __tablename__ = "market_price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to active market
    market_id = Column(String, nullable=False, index=True)  # References ActiveMarket.market_id

    # Price snapshot
    timestamp = Column(DateTime, nullable=False, index=True)  # When this price was observed
    away_price = Column(Float, nullable=False)  # Away team win probability (0-1)
    home_price = Column(Float, nullable=False)  # Home team win probability (0-1)
    mid_price = Column(Float, nullable=False)  # (away_price + home_price) / 2

    # Optional: Trading volume data if available
    volume = Column(Float, nullable=True)  # Trading volume at this timestamp


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
            - game_start_ts (datetime)
            - market_open_ts (datetime, optional)
            - market_close_ts (datetime, optional)
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
                now = datetime.utcnow()
                market = ActiveMarket(
                    market_id=market_data['market_id'],
                    polymarket_slug=market_data['polymarket_slug'],
                    sport=market_data['sport'],
                    game_date=market_data['game_date'],
                    away_team=market_data['away_team'],
                    away_team_id=market_data.get('away_team_id'),
                    home_team=market_data['home_team'],
                    home_team_id=market_data.get('home_team_id'),
                    game_start_ts=market_data['game_start_ts'],
                    market_open_ts=market_data.get('market_open_ts'),
                    market_close_ts=market_data.get('market_close_ts'),
                    market_status=market_data.get('market_status', 'open'),
                    last_updated=now,
                    created_at=now
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


def insert_price_snapshot(market_id: str, timestamp, away_price: float, home_price: float) -> bool:
    """
    Insert a single price snapshot for a market.

    Args:
        market_id: Polymarket market ID
        timestamp: datetime when price was observed
        away_price: Away team price (0-1)
        home_price: Home team price (0-1)

    Returns:
        True if inserted successfully, False otherwise
    """
    from datetime import datetime

    session = SessionLocal()

    try:
        mid_price = (away_price + home_price) / 2

        snapshot = MarketPriceHistory(
            market_id=market_id,
            timestamp=timestamp,
            away_price=away_price,
            home_price=home_price,
            mid_price=mid_price
        )
        session.add(snapshot)

        # Update last_updated in ActiveMarket
        market = session.query(ActiveMarket).filter_by(market_id=market_id).first()
        if market:
            market.last_updated = datetime.utcnow()

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error inserting price snapshot for market {market_id}: {e}")
        return False
    finally:
        session.close()


def get_active_markets(status: str = 'open') -> list[dict]:
    """
    Retrieve list of active markets to track.

    Args:
        status: Filter by market status ('open', 'closed', 'resolved'). Default 'open'.

    Returns:
        List of market dicts with all fields from ActiveMarket table
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
