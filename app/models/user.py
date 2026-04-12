"""SQLAlchemy models for users, candidate_profiles, and recruiter_profiles."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text, ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """Core user record — linked to Firebase Auth via firebase_uid."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(Enum("candidate", "recruiter", name="user_role"), nullable=True)
    avatar_url = Column(Text, nullable=True)
    onboarding_complete = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)
    referral_code = Column(String(12), unique=True, nullable=True, index=True)
    referred_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    xp_points = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    candidate_profile = relationship("CandidateProfile", back_populates="user", uselist=False, lazy="selectin")
    recruiter_profile = relationship("RecruiterProfile", back_populates="user", uselist=False, lazy="selectin")


class CandidateProfile(Base):
    """Extended profile for candidates."""

    __tablename__ = "candidate_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    headline = Column(String(120), nullable=True)
    bio = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    github_url = Column(Text, nullable=True)
    linkedin_url = Column(Text, nullable=True)
    portfolio_url = Column(Text, nullable=True)
    skill_tags = Column(ARRAY(String), default=list, nullable=False)
    career_goal = Column(String(60), nullable=True)
    skill_score = Column(Integer, default=0, nullable=False)
    scores = Column(JSONB, nullable=True)
    public_profile = Column(Boolean, default=True, nullable=False)
    notification_prefs = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="candidate_profile")


class RecruiterProfile(Base):
    """Extended profile for recruiters."""

    __tablename__ = "recruiter_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    company_name = Column(String(120), nullable=True)
    company_size = Column(String(20), nullable=True)
    role_at_company = Column(String(100), nullable=True)
    hiring_domains = Column(ARRAY(String), default=list, nullable=False)
    company_website = Column(Text, nullable=True)
    # Part 5 — subscription
    subscription_plan = Column(String(30), nullable=True)       # starter, growth, enterprise
    subscription_status = Column(String(30), nullable=True)     # active, cancelled, payment_failed, expired
    subscription_id = Column(String(100), nullable=True)        # Razorpay subscription ID
    subscription_valid_until = Column(DateTime, nullable=True)
    active_task_limit = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="recruiter_profile")
