"""Pydantic schemas for leaderboard and ELO endpoints."""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class LeaderboardRow(BaseModel):
    """Single row in a leaderboard."""
    rank: int
    user_id: str
    name: str
    avatar: Optional[str]
    country: Optional[str]
    elo: int
    tier: str
    win_rate: float
    matches_played: int


class LeaderboardResponse(BaseModel):
    """Leaderboard page response."""
    rows: List[LeaderboardRow]
    total_count: int
    user_row: Optional[LeaderboardRow]


class UserRankResponse(BaseModel):
    """User's full rank and ELO data."""
    elo: int
    tier: str
    global_rank: Optional[int]
    country_rank: Optional[int]
    weekly_gain: int
    monthly_gain: int
    placement_matches_remaining: Optional[int]
    season_end_date: Optional[date]
    days_remaining: Optional[int]
    matches_played: int
    wins: int
    losses: int
    draws: int
    peak_elo: int
    current_streak: int


class EloHistoryItem(BaseModel):
    """Single ELO change event."""
    date: datetime
    elo_before: int
    elo_after: int
    change: int
    source: str
    opponent_name: Optional[str]


class EloHistoryResponse(BaseModel):
    """ELO history list."""
    items: List[EloHistoryItem]


class EloBreakdownResponse(BaseModel):
    """ELO earned by source category."""
    from_1v1: int
    from_daily: int
    from_weekly: int
    from_monthly: int
    from_bonuses: int


class SeasonResponse(BaseModel):
    """Current season info."""
    season_number: int
    start_date: date
    end_date: date
    days_remaining: int
    current_elo: int
    projected_elo_after_reset: int
