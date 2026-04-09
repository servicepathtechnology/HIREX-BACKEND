"""SQLAlchemy models for tasks, submissions, bookmarks, and skill_score_history."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(160), nullable=False)
    slug = Column(String(180), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    problem_statement = Column(Text, nullable=False)
    evaluation_criteria = Column(JSONB, nullable=False)
    domain = Column(String(60), nullable=False)
    difficulty = Column(
        Enum("beginner", "intermediate", "advanced", "expert", name="task_difficulty"),
        nullable=False,
    )
    task_type = Column(
        Enum("code", "design", "case_study", "business", "product", "writing", name="task_type_enum"),
        nullable=False,
    )
    submission_types = Column(ARRAY(String), nullable=False)
    max_file_size_mb = Column(Integer, default=10)
    allowed_file_types = Column(ARRAY(String), nullable=True)
    deadline = Column(DateTime, nullable=False)
    max_submissions = Column(Integer, nullable=True)
    is_published = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    skills_tested = Column(ARRAY(String), nullable=False)
    estimated_hours = Column(Float, nullable=True)
    company_visible = Column(Boolean, default=False)
    company_name = Column(String(120), nullable=True)
    prize_or_opportunity = Column(Text, nullable=True)
    tier = Column(String(20), default="standard", nullable=False)
    view_count = Column(Integer, default=0)
    submission_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    submissions = relationship("Submission", back_populates="task")
    bookmarks = relationship("Bookmark", back_populates="task")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum("draft", "submitted", "under_review", "scored", "rejected", name="submission_status"),
        nullable=False,
        default="draft",
    )
    text_content = Column(Text, nullable=True)
    code_content = Column(Text, nullable=True)
    code_language = Column(String(40), nullable=True)
    file_urls = Column(ARRAY(String), nullable=True)
    link_url = Column(Text, nullable=True)
    recording_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    score_accuracy = Column(Float, nullable=True)
    score_approach = Column(Float, nullable=True)
    score_completeness = Column(Float, nullable=True)
    score_efficiency = Column(Float, nullable=True)
    total_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    percentile = Column(Float, nullable=True)
    recruiter_feedback = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    time_spent_minutes = Column(Integer, nullable=True)
    is_shortlisted = Column(Boolean, default=False)
    content_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="submissions")
    candidate = relationship("User", foreign_keys=[candidate_id])
    skill_score_history = relationship("SkillScoreHistory", back_populates="submission")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="bookmarks")
    candidate = relationship("User", foreign_keys=[candidate_id])


class SkillScoreHistory(Base):
    __tablename__ = "skill_score_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    domain = Column(String(60), nullable=False)
    score = Column(Integer, nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submission = relationship("Submission", back_populates="skill_score_history")
    candidate = relationship("User", foreign_keys=[candidate_id])
