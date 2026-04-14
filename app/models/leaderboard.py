"""SQLAlchemy models for Part 3 — Global Leaderboards + Ranking Tiers."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Date, ForeignKey,
    Integer, String, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Season(Base):
    """90-day competitive seasons with soft ELO resets."""

    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_number = Column(Integer, unique=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    reset_factor = Column(Numeric(3, 2), nullable=False, default=0.20)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EloEvent(Base):
    """Immutable log of every ELO change event."""

    __tablename__ = "elo_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    elo_before = Column(Integer, nullable=False)
    elo_change = Column(Integer, nullable=False)
    elo_after = Column(Integer, nullable=False)
    tier_before = Column(String(20), nullable=False)
    tier_after = Column(String(20), nullable=True)
    opponent_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=True)
    challenge_id = Column(UUID(as_uuid=True), nullable=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    opponent = relationship("User", foreign_keys=[opponent_id], lazy="selectin")
    season = relationship("Season", lazy="selectin")


class TierHistory(Base):
    """Records every tier promotion/demotion."""

    __tablename__ = "tier_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tier_from = Column(String(20), nullable=False)
    tier_to = Column(String(20), nullable=False)
    elo_at_change = Column(Integer, nullable=False)
    direction = Column(String(10), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    season = relationship("Season", lazy="selectin")


class SeasonResult(Base):
    """Snapshot of user standings at season end."""

    __tablename__ = "season_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    final_elo = Column(Integer, nullable=False)
    final_tier = Column(String(20), nullable=False)
    global_rank = Column(Integer, nullable=True)
    country_rank = Column(Integer, nullable=True)
    elo_gained = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    season = relationship("Season", lazy="selectin")


class LeaderboardCacheMeta(Base):
    """Tracks when each leaderboard type was last refreshed."""

    __tablename__ = "leaderboard_cache_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_type = Column(String(30), unique=True, nullable=False)
    last_computed = Column(DateTime, nullable=False)
    total_entries = Column(Integer, nullable=False, default=0)
