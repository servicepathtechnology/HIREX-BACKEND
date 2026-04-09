"""Pydantic v2 schemas for auth and user endpoints."""

from __future__ import annotations
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Payload sent after Firebase signup to create the DB record."""

    firebase_uid: str
    email: EmailStr
    full_name: str
    referral_code: Optional[str] = None  # Referral code from the inviter


class UpdateUserRequest(BaseModel):
    """Fields that can be updated via PUT /api/v1/auth/me."""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    avatar_url: Optional[str] = None
    onboarding_complete: Optional[bool] = None
    is_verified: Optional[bool] = None

    # Candidate profile fields
    headline: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    skill_tags: Optional[List[str]] = None
    career_goal: Optional[str] = None
    public_profile: Optional[bool] = None

    # Recruiter profile fields
    company_name: Optional[str] = None
    company_size: Optional[str] = None
    role_at_company: Optional[str] = None
    hiring_domains: Optional[List[str]] = None
    company_website: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("candidate", "recruiter"):
            raise ValueError("role must be 'candidate' or 'recruiter'")
        return v


class CandidateProfileResponse(BaseModel):
    """Candidate profile data returned in /me responses."""

    headline: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    skill_tags: List[str] = []
    career_goal: Optional[str] = None
    skill_score: int = 0
    public_profile: bool = True

    model_config = {"from_attributes": True}


class RecruiterProfileResponse(BaseModel):
    """Recruiter profile data returned in /me responses."""

    company_name: Optional[str] = None
    company_size: Optional[str] = None
    role_at_company: Optional[str] = None
    hiring_domains: List[str] = []
    company_website: Optional[str] = None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """Full user response including nested profile."""

    id: UUID
    firebase_uid: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: Optional[str] = None
    avatar_url: Optional[str] = None
    onboarding_complete: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    candidate_profile: Optional[CandidateProfileResponse] = None
    recruiter_profile: Optional[RecruiterProfileResponse] = None

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    environment: str
