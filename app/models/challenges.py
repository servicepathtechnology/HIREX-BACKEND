"""SQLAlchemy models for Part 1 — 1v1 Live Challenges."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChallengeTask(Base):
    """Pre-seeded challenge tasks assigned to matches."""

    __tablename__ = "challenge_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(
        Enum("coding", "design", "product", "marketing", "data", "writing",
             name="challenge_domain"),
        nullable=False,
        index=True,
    )
    difficulty = Column(
        Enum("easy", "medium", "hard", name="challenge_difficulty"),
        nullable=False,
        default="easy",
        index=True,
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    evaluation_criteria = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    matches = relationship("Match", back_populates="challenge_task", lazy="selectin")


class Match(Base):
    """A 1v1 challenge match between two candidates."""

    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenger_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    opponent_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    domain = Column(
        Enum("coding", "design", "product", "marketing", "data", "writing",
             name="challenge_domain"),
        nullable=False,
    )
    task_id = Column(UUID(as_uuid=True), ForeignKey("challenge_tasks.id"), nullable=True)
    difficulty = Column(
        Enum("easy", "medium", "hard", name="challenge_difficulty"),
        nullable=False,
        default="easy",
    )
    duration_minutes = Column(Integer, nullable=False, default=30)
    status = Column(
        Enum("pending", "active", "completed", "cancelled", "expired",
             name="match_status"),
        nullable=False,
        default="pending",
        index=True,
    )
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    challenger_elo_before = Column(Integer, nullable=False, default=1000)
    opponent_elo_before = Column(Integer, nullable=False, default=1000)
    challenger_elo_after = Column(Integer, nullable=True)
    opponent_elo_after = Column(Integer, nullable=True)
    invite_message = Column(String(200), nullable=True)
    decline_reason = Column(String(100), nullable=True)
    challenge_link = Column(Text, nullable=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True)
    spectator_count = Column(Integer, default=0, nullable=False)
    winner_points = Column(Integer, default=0, nullable=True)
    challenge_badge = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # selectin loading is required for async SQLAlchemy — avoids lazy-load errors
    challenger = relationship("User", foreign_keys=[challenger_id], lazy="selectin")
    opponent = relationship("User", foreign_keys=[opponent_id], lazy="selectin")
    winner = relationship("User", foreign_keys=[winner_id], lazy="selectin")
    challenge_task = relationship("ChallengeTask", back_populates="matches", lazy="selectin")
    question = relationship("Question", foreign_keys=[question_id], lazy="selectin")
    submissions = relationship("ChallengeSubmission", back_populates="match", lazy="selectin")


class ChallengeSubmission(Base):
    """A candidate's submission for a challenge match."""

    __tablename__ = "challenge_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False, default="")
    language = Column(String(40), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    score = Column(Integer, nullable=True)
    score_breakdown = Column(JSONB, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    is_auto = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_challenge_submission_match_user"),
    )

    match = relationship("Match", back_populates="submissions", lazy="selectin")
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class UserElo(Base):
    """ELO rating record — one row per user."""

    __tablename__ = "user_elo"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    elo = Column(Integer, nullable=False, default=1000)
    tier = Column(
        Enum("bronze", "silver", "gold", "platinum", "diamond", "elite",
             name="elo_tier"),
        nullable=False,
        default="silver",
    )
    matches_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)
    peak_elo = Column(Integer, nullable=False, default=1000)
    current_streak = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # selectin for async-safe eager loading
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class Question(Base):
    """Full coding question with test cases — PRD §7.5."""

    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    difficulty = Column(String(10), nullable=False, index=True)
    problem_statement = Column(Text, nullable=False)
    constraints = Column(Text, nullable=True)
    input_format = Column(Text, nullable=True)
    output_format = Column(Text, nullable=True)
    sample_input_1 = Column(Text, nullable=True)
    sample_output_1 = Column(Text, nullable=True)
    sample_input_2 = Column(Text, nullable=True)
    sample_output_2 = Column(Text, nullable=True)
    test_cases = Column(JSONB, nullable=True)   # [{input, expected_output}] — HIDDEN
    time_limit_ms = Column(Integer, nullable=False, default=2000)
    memory_limit_mb = Column(Integer, nullable=False, default=256)
    editorial = Column(Text, nullable=True)
    tags = Column(JSONB, nullable=True)         # list of strings
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuestionHistory(Base):
    """Tracks which questions each user has seen — prevents repeats within 30 days."""

    __tablename__ = "question_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False)
    seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ChallengeBadge(Base):
    """Badge definitions for 1v1 challenges."""

    __tablename__ = "challenge_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(Text, nullable=True)
    condition = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserChallengeBadge(Base):
    """Earned 1v1 challenge badges per user."""

    __tablename__ = "user_challenge_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    badge_slug = Column(String(50), nullable=False)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=True)
    earned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "badge_slug", name="uq_user_badge"),
    )
