from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

BolaoLabel = Literal["1", "X", "2"]


class BronzeArticle(BaseModel):
    id: str
    source: str
    source_url: HttpUrl
    title: str
    summary: Optional[str] = None
    content_raw: Optional[str] = None
    published_at: Optional[datetime] = None
    scraped_at: datetime
    content_hash: str
    raw_payload: dict = Field(default_factory=dict)


class SilverArticle(BaseModel):
    id: str
    source: str
    source_url: HttpUrl
    title: str
    body: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    scraped_at: datetime
    content_hash: str
    teams_mentioned: list[str] = Field(default_factory=list)
    players_mentioned: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None


class BolaoFeature(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    round_number: int
    competition: str
    match_date: datetime
    news_count_home: int = 0
    news_count_away: int = 0
    injury_mentions_home: int = 0
    injury_mentions_away: int = 0
    sentiment_home: Optional[float] = None
    sentiment_away: Optional[float] = None
    headline_keywords: list[str] = Field(default_factory=list)
    home_position: Optional[int] = None
    away_position: Optional[int] = None
    home_points: Optional[int] = None
    away_points: Optional[int] = None
    home_form: Optional[str] = None
    away_form: Optional[str] = None
    home_goals_for: Optional[int] = None
    home_goals_against: Optional[int] = None
    away_goals_for: Optional[int] = None
    away_goals_against: Optional[int] = None
    h2h_home_wins: Optional[int] = None
    h2h_draws: Optional[int] = None
    h2h_away_wins: Optional[int] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None
    home_possession_pct: Optional[int] = None
    away_possession_pct: Optional[int] = None


class GoldBolaoContext(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    round_number: int
    competition: str
    match_date: datetime
    context_text: str
    features: BolaoFeature
    label: Optional[BolaoLabel] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    season: Optional[int] = None


class MatchResult(BaseModel):
    match_id: str
    season: int
    competition: str
    round_number: int
    match_date: datetime
    home_team: str
    away_team: str
    home_team_raw: str
    away_team_raw: str
    home_score: int
    away_score: int
    label: BolaoLabel
    imported_at: datetime
    phase: str = "group"
    group_name: Optional[str] = None
    is_neutral: bool = True
