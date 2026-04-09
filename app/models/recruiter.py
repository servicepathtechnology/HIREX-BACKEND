"""SQLAlchemy models for Part 3 — task_payments, pipeline_entries, notifications, recruiter_analytics."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class TaskPayment(Base):
    __tablename__ = "task_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    razorpay_order_id = Column(String(100), unique=True, nullable=False)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(300), nullable=True)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String(10), default="INR")
    status = Column(
        Enum("pending", "paid", "failed", "refunded", name="payment_status"),
        default="pending",
        nullable=False,
    )
    tier = Column(String(40), nullable=False)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    recruiter = relationship("User", foreign_keys=[recruiter_id])
    task = relationship("Task", foreign_keys=[task_id])


class PipelineEntry(Base):
    __tablename__ = "pipeline_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False)
    stage = Column(
        Enum("shortlisted", "interviewing", "offer_sent", "hired", "rejected", name="pipeline_stage"),
        default="shortlisted",
        nullable=False,
    )
    recruiter_notes = Column(Text, nullable=True)
    stage_updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "candidate_id", "task_id", name="uq_pipeline_recruiter_candidate_task"),
    )

    recruiter = relationship("User", foreign_keys=[recruiter_id])
    candidate = relationship("User", foreign_keys=[candidate_id])
    task = relationship("Task", foreign_keys=[task_id])
    submission = relationship("Submission", foreign_keys=[submission_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(80), nullable=False)
    title = Column(String(160), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSONB, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])


class RecruiterAnalytics(Base):
    __tablename__ = "recruiter_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), unique=True, nullable=False)
    total_views = Column(Integer, default=0)
    total_submissions = Column(Integer, default=0)
    scored_count = Column(Integer, default=0)
    shortlisted_count = Column(Integer, default=0)
    hired_count = Column(Integer, default=0)
    avg_score = Column(Float, nullable=True)
    score_distribution = Column(JSONB, nullable=True)
    avg_time_spent_mins = Column(Float, nullable=True)
    time_to_first_submission_hours = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    task = relationship("Task", foreign_keys=[task_id])
