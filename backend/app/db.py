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

    id = Column(Integer, primary_key=True, autoincrement=True)

    sport = Column(String, nullable=False)  
    season = Column(Integer, nullable=True)

    game_id = Column(String, nullable=False)
    game_date = Column(Date)

    home_team_id = Column(String, nullable=False)
    away_team_id = Column(String, nullable=False)

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

    home_team_price = Column(Float)
    away_team_price = Column(Float)

    start_ts = Column(DateTime)
    market_open_ts = Column(DateTime)


def prepare_nba_df_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform basketball_api DataFrame to match NBAGameFeatures schema.

    Transformations:
    - Convert column names to lowercase
    - Add 'sport' column with value 'NBA'
    - Add 'season' column (start year of NBA season)
    - Convert Unix timestamps to DateTime objects

    Args:
        df: DataFrame from basketball_api.get_matchups_cumulative_stats_between()

    Returns:
        Transformed DataFrame ready for database insertion
    """
    df_copy = df.copy()

    # Convert column names to lowercase
    df_copy.columns = df_copy.columns.str.lower()

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
    if 'start_ts' in df_copy.columns:
        df_copy['start_ts'] = pd.to_datetime(
            df_copy['start_ts'],
            unit='s',
            errors='coerce'
        )
    if 'market_open_ts' in df_copy.columns:
        df_copy['market_open_ts'] = pd.to_datetime(
            df_copy['market_open_ts'],
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


class NFLGameFeatures(Base):
    pass
