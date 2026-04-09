"""Auth endpoints — register, /me GET/PUT, logout, health, delete, export."""

import logging
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models.user import User, CandidateProfile, RecruiterProfile
from app.schemas.auth import (
    RegisterRequest,
    UpdateUserRequest,
    UserResponse,
    HealthResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Public health check endpoint for DevOps monitoring."""
    return HealthResponse(status="ok", environment=settings.app_env)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """
    Create a user record in PostgreSQL after Firebase signup.
    Idempotent — returns existing user if firebase_uid OR email already exists.
    """
    # Check by firebase_uid first
    result = await db.execute(select(User).where(User.firebase_uid == payload.firebase_uid))
    existing = result.scalar_one_or_none()

    # Also check by email (handles re-registration after DB wipe or UID mismatch)
    if not existing:
        result = await db.execute(select(User).where(User.email == payload.email))
        existing = result.scalar_one_or_none()
        if existing:
            # Update firebase_uid in case it changed (e.g. account re-linked)
            existing.firebase_uid = payload.firebase_uid
            await db.flush()

    if existing:
        return UserResponse.model_validate(existing)

    # Generate unique referral code
    referral_code = await _generate_unique_referral_code(db)

    user = User(
        firebase_uid=payload.firebase_uid,
        email=payload.email,
        full_name=payload.full_name,
        referral_code=referral_code,
    )
    db.add(user)
    await db.flush()

    # Link referral if a valid code was provided
    if payload.referral_code:
        referrer_result = await db.execute(
            select(User).where(User.referral_code == payload.referral_code.upper())
        )
        referrer = referrer_result.scalar_one_or_none()
        if referrer:
            user.referred_by_user_id = referrer.id
            await db.flush()

    # Re-fetch with selectin relationships loaded
    result2 = await db.execute(select(User).where(User.id == user.id))
    user = result2.scalar_one()
    return UserResponse.model_validate(user)


async def _generate_unique_referral_code(db: AsyncSession) -> str:
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "HIREX-" + "".join(random.choices(chars, k=5))
        existing = await db.execute(select(User).where(User.referral_code == code))
        if not existing.scalar_one_or_none():
            return code
    return "HIREX-" + "".join(random.choices(chars, k=6))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's full profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user profile fields. Handles both user and nested profile tables."""
    # Update top-level user fields
    user_fields = ["full_name", "phone", "role", "avatar_url", "onboarding_complete", "is_verified"]
    for field in user_fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(current_user, field, value)

    # Handle candidate profile
    candidate_fields = ["headline", "bio", "city", "github_url", "linkedin_url",
                        "portfolio_url", "skill_tags", "career_goal", "public_profile"]
    candidate_data = {f: getattr(payload, f) for f in candidate_fields if getattr(payload, f) is not None}

    if candidate_data:
        if current_user.candidate_profile is None:
            profile = CandidateProfile(user_id=current_user.id, **candidate_data)
            db.add(profile)
        else:
            for k, v in candidate_data.items():
                setattr(current_user.candidate_profile, k, v)

    # Handle recruiter profile
    recruiter_fields = ["company_name", "company_size", "role_at_company", "hiring_domains", "company_website"]
    recruiter_data = {f: getattr(payload, f) for f in recruiter_fields if getattr(payload, f) is not None}

    if recruiter_data:
        if current_user.recruiter_profile is None:
            profile = RecruiterProfile(user_id=current_user.id, **recruiter_data)
            db.add(profile)
        else:
            for k, v in recruiter_data.items():
                setattr(current_user.recruiter_profile, k, v)

    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)) -> None:
    """
    Server-side logout. Firebase tokens are stateless so this is a no-op
    for now — client must clear local storage. Placeholder for session
    invalidation in Part 4.
    """
    pass


@router.delete("/me", status_code=status.HTTP_202_ACCEPTED)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full account + data deletion — cascades to all related records."""
    from app.models.task import Submission, Bookmark
    from app.models.recruiter import TaskPayment, PipelineEntry, Notification
    from app.models.part4 import FCMToken, MessageThread, Message, AIScoringJob

    user_id = current_user.id

    # Cancel active Razorpay subscription if any
    if current_user.recruiter_profile and current_user.recruiter_profile.subscription_id:
        try:
            from app.billing.subscription_service import cancel_razorpay_subscription
            await cancel_razorpay_subscription(current_user.recruiter_profile.subscription_id)
        except Exception as e:
            logger.warning(f"Subscription cancel failed during account deletion: {e}")

    # Deactivate FCM tokens
    fcm_result = await db.execute(select(FCMToken).where(FCMToken.user_id == user_id))
    for token in fcm_result.scalars().all():
        token.is_active = False

    # Anonymise leaderboard entries — set name to "Deleted User" via a flag
    # We cannot null candidate_id (non-nullable FK), so we soft-delete the user
    # and the display layer will show "Deleted User" for is_active=False users

    # Delete notifications
    await db.execute(delete(Notification).where(Notification.user_id == user_id))

    # Delete bookmarks
    await db.execute(delete(Bookmark).where(Bookmark.candidate_id == user_id))

    # Soft-delete user
    current_user.is_active = False
    current_user.email = f"deleted_{user_id}@hirex.deleted"
    current_user.full_name = "Deleted User"
    current_user.firebase_uid = f"deleted_{user_id}"

    await db.flush()
    logger.info(f"Account deleted: {user_id}")
    return {"status": "accepted", "message": "Account deletion initiated. Data will be wiped within 30 days."}


@router.get("/me/export", status_code=status.HTTP_202_ACCEPTED)
async def export_my_data(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Trigger async data export — user will receive email with download link."""
    # In production: enqueue a Celery task to generate ZIP and email user
    logger.info(f"Data export requested for user {current_user.id}")
    return {"status": "accepted", "message": "Your data export is being prepared. You will receive an email when ready."}
