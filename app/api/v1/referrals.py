"""Referral system endpoints — codes, stats, rewards."""

import random
import string
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.part5 import ReferralReward

router = APIRouter(prefix="/referrals", tags=["referrals"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReferralStatsResponse(BaseModel):
    referral_code: str
    total_referred: int
    total_joined: int
    rewards_earned: int


class ReferralRewardResponse(BaseModel):
    id: str
    reward_type: str
    reward_value: Optional[str]
    status: str
    referred_user_name: Optional[str]
    created_at: datetime
    issued_at: Optional[datetime]


class ValidateReferralRequest(BaseModel):
    referral_code: str


class ValidateReferralResponse(BaseModel):
    valid: bool
    referrer_name: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=5))
    return f"HIREX-{suffix}"


async def ensure_referral_code(user: User, db: AsyncSession) -> str:
    if user.referral_code:
        return user.referral_code
    # Generate unique code
    for _ in range(10):
        code = _generate_referral_code()
        existing = await db.execute(select(User).where(User.referral_code == code))
        if not existing.scalar_one_or_none():
            user.referral_code = code
            await db.flush()
            return code
    raise HTTPException(status_code=500, detail="Could not generate referral code.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=ReferralStatsResponse)
async def get_my_referral_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReferralStatsResponse:
    code = await ensure_referral_code(current_user, db)

    # Count referred users
    total_referred_result = await db.execute(
        select(func.count(User.id)).where(User.referred_by_user_id == current_user.id)
    )
    total_referred = total_referred_result.scalar() or 0

    # Count those who completed onboarding (joined)
    total_joined_result = await db.execute(
        select(func.count(User.id)).where(
            User.referred_by_user_id == current_user.id,
            User.onboarding_complete == True,
        )
    )
    total_joined = total_joined_result.scalar() or 0

    # Count issued rewards
    rewards_result = await db.execute(
        select(func.count(ReferralReward.id)).where(
            ReferralReward.referrer_id == current_user.id,
            ReferralReward.status == "issued",
        )
    )
    rewards_earned = rewards_result.scalar() or 0

    return ReferralStatsResponse(
        referral_code=code,
        total_referred=total_referred,
        total_joined=total_joined,
        rewards_earned=rewards_earned,
    )


@router.get("/rewards", response_model=List[ReferralRewardResponse])
async def get_my_rewards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ReferralRewardResponse]:
    result = await db.execute(
        select(ReferralReward).where(
            ReferralReward.referrer_id == current_user.id
        ).order_by(ReferralReward.created_at.desc())
    )
    rewards = result.scalars().all()

    items = []
    for r in rewards:
        referred_result = await db.execute(select(User).where(User.id == r.referred_id))
        referred_user = referred_result.scalar_one_or_none()
        items.append(ReferralRewardResponse(
            id=str(r.id),
            reward_type=r.reward_type,
            reward_value=r.reward_value,
            status=r.status,
            referred_user_name=referred_user.full_name if referred_user else None,
            created_at=r.created_at,
            issued_at=r.issued_at,
        ))
    return items


@router.post("/validate", response_model=ValidateReferralResponse)
async def validate_referral_code(
    payload: ValidateReferralRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidateReferralResponse:
    result = await db.execute(
        select(User).where(User.referral_code == payload.referral_code.upper())
    )
    user = result.scalar_one_or_none()
    if not user:
        return ValidateReferralResponse(valid=False)
    return ValidateReferralResponse(valid=True, referrer_name=user.full_name)
