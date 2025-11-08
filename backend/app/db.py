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

class NFLGameFeatures(Base):
    pass
