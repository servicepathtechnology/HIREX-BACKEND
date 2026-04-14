"""SQLAlchemy models for Part 2 — Daily/Weekly/Monthly Challenges + Streaks."""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class DailyChallenge(Base):
    """One row per calendar day — the assigned question for that day."""

    __tablename__ = "daily_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_date = Column(Date, unique=True, nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    question = relationship("Question", foreign_keys=[question_id], lazy="selectin")


class WeeklyChallenge(Base):
    """One row per ISO calendar week."""

    __tablename__ = "weekly_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year = Column(Integer, nullable=False)
    week_number = Column(Integer, nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("year", "week_number", name="uq_weekly_year_week"),
    )

    question = relationship("Question", foreign_keys=[question_id], lazy="selectin")


class MonthlyChallenge(Base):
    """One row per calendar month."""

    __tablename__ = "monthly_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_monthly_year_month"),
    )

    question = relationship("Question", foreign_keys=[question_id], lazy="selectin")


class UserChallenge(Base):
    """Each user's attempt at a daily/weekly/monthly challenge."""

    __tablename__ = "user_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    challenge_type = Column(String(10), nullable=False)  # daily | weekly | monthly
    challenge_ref_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(20), nullable=False, default="not_started")
    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    room_token = Column(Text, nullable=True)
    room_url = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    tests_passed = Column(Integer, nullable=True)
    tests_total = Column(Integer, nullable=True)
    result_status = Column(String(30), nullable=True)
    time_taken_sec = Column(Integer, nullable=True)
    xp_earned = Column(Integer, default=0, nullable=False)
    language = Column(String(20), nullable=True)
    code_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    judge_job_ids = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "challenge_type", "challenge_ref_id",
                         name="uq_user_challenge_dedup"),
    )

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class UserStreak(Base):
    """Streak record — one row per user."""

    __tablename__ = "user_streaks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_activity_date = Column(Date, nullable=True)
    grace_day_available = Column(Boolean, nullable=False, default=True)
    grace_day_used_date = Column(Date, nullable=True)
    streak_started_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class StreakHistory(Base):
    """Log of every streak event for heatmap and history display."""

    __tablename__ = "streak_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    event_date = Column(Date, nullable=False)
    event_type = Column(String(20), nullable=False)
    streak_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserPreferences(Base):
    """User scheduling preferences for weekly/monthly challenges."""

    __tablename__ = "user_preferences"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    weekly_day = Column(String(10), nullable=True)
    monthly_date = Column(Integer, nullable=True)
    notification_time = Column(String(5), nullable=False, default="09:00")
    timezone = Column(String(60), nullable=False, default="UTC")
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class QuestionScheduleHistory(Base):
    """Tracks which questions have been used to prevent repeats."""

    __tablename__ = "question_schedule_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    challenge_type = Column(String(10), nullable=False)
    used_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
