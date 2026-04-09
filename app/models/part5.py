"""SQLAlchemy models for Part 5 — subscriptions, referrals, admin, OG images."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referred_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reward_type = Column(String(60), nullable=False)   # spotlight, cashback, free_task, score_bonus, discount
    reward_value = Column(String(100), nullable=True)  # e.g. "500", "50", "20%"
    status = Column(
        Enum("pending", "issued", "expired", name="reward_status"),
        default="pending", nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    issued_at = Column(DateTime, nullable=True)

    referrer = relationship("User", foreign_keys=[referrer_id])
    referred = relationship("User", foreign_keys=[referred_id])


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_email = Column(String(255), nullable=False)
    action = Column(String(120), nullable=False)
    target_type = Column(String(60), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
