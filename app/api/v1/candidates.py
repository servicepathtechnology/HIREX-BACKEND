"""
Candidate search endpoint — supports search by name, email, user ID,
Firebase UID, and referral code. Used by the 1v1 Challenges feature
to find opponents.

GET /api/v1/candidates/search?q=<query>&limit=10&exclude_self=true
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, CandidateProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])

# ── Response schema ───────────────────────────────────────────────────────────

class CandidateSearchResult(BaseModel):
    id: str
    firebase_uid: str
    full_name: str
    email: str
    avatar_url: Optional[str] = None
    headline: Optional[str] = None
    city: Optional[str] = None
    skill_tags: list[str] = []
    skill_score: int = 0
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class CandidateSearchResponse(BaseModel):
    results: list[CandidateSearchResult]
    total: int
    query: str


# ── Helpers ───────────────────────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_REFERRAL_RE = re.compile(r"^HIREX-[A-Z0-9]{5,6}$", re.IGNORECASE)


def _is_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(s.strip()))


def _is_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s.strip()))


def _is_referral_code(s: str) -> bool:
    return bool(_REFERRAL_RE.match(s.strip()))


def _build_result(user: User) -> CandidateSearchResult:
    profile: CandidateProfile | None = user.candidate_profile
    return CandidateSearchResult(
        id=str(user.id),
        firebase_uid=user.firebase_uid,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        headline=profile.headline if profile else None,
        city=profile.city if profile else None,
        skill_tags=profile.skill_tags if profile else [],
        skill_score=profile.skill_score if profile else 0,
        role=user.role,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/search", response_model=CandidateSearchResponse)
async def search_candidates(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(default=10, ge=1, le=50),
    exclude_self: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateSearchResponse:
    """
    Universal candidate search.

    Supports:
    - Full name (partial, case-insensitive)
    - Email (exact or partial)
    - User UUID (exact)
    - Firebase UID (exact)
    - Referral code (exact, e.g. HIREX-AB12C)

    Only returns active, onboarded candidates with public profiles.
    Excludes the requesting user when exclude_self=true.
    """
    q = q.strip()
    users: list[User] = []

    # ── Strategy 1: Exact UUID lookup ─────────────────────────────────────────
    if _is_uuid(q):
        try:
            uid = uuid.UUID(q)
            result = await db.execute(
                select(User).where(
                    User.id == uid,
                    User.is_active == True,
                    User.onboarding_complete == True,
                )
            )
            user = result.scalar_one_or_none()
            if user:
                users = [user]
        except ValueError:
            pass

    # ── Strategy 2: Exact email lookup ────────────────────────────────────────
    elif _is_email(q):
        result = await db.execute(
            select(User).where(
                func.lower(User.email) == q.lower(),
                User.is_active == True,
                User.onboarding_complete == True,
            )
        )
        user = result.scalar_one_or_none()
        if user:
            users = [user]

    # ── Strategy 3: Referral code lookup ─────────────────────────────────────
    elif _is_referral_code(q):
        result = await db.execute(
            select(User).where(
                func.upper(User.referral_code) == q.upper(),
                User.is_active == True,
                User.onboarding_complete == True,
            )
        )
        user = result.scalar_one_or_none()
        if user:
            users = [user]

    # ── Strategy 4: Firebase UID (exact, long string, no spaces) ─────────────
    elif len(q) >= 20 and " " not in q and not _is_uuid(q):
        result = await db.execute(
            select(User).where(
                User.firebase_uid == q,
                User.is_active == True,
                User.onboarding_complete == True,
            )
        )
        user = result.scalar_one_or_none()
        if user:
            users = [user]

        # If no exact firebase UID match, fall through to name search
        if not users:
            users = await _name_search(db, q, limit)

    # ── Strategy 5: Full-text name / email partial search ────────────────────
    else:
        users = await _name_search(db, q, limit)

    # ── Exclude self ──────────────────────────────────────────────────────────
    if exclude_self:
        users = [u for u in users if u.id != current_user.id]

    # ── Exclude non-candidates (only show candidates for challenge search) ────
    # Allow all roles so recruiters can also be challenged if they have a profile
    # but filter out users with no role set (incomplete onboarding edge case)
    users = [u for u in users if u.role is not None]

    results = [_build_result(u) for u in users[:limit]]

    return CandidateSearchResponse(
        results=results,
        total=len(results),
        query=q,
    )


async def _name_search(db: AsyncSession, q: str, limit: int) -> list[User]:
    """
    Fuzzy name + partial email search using PostgreSQL ILIKE.
    Ranks exact-start matches above contains matches.
    """
    pattern = f"%{q}%"
    starts_with = f"{q}%"

    # Fetch candidates matching name or email
    stmt = (
        select(User)
        .where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            ),
            User.is_active == True,
            User.onboarding_complete == True,
        )
        .limit(limit * 2)  # fetch extra to allow re-ranking
    )
    result = await db.execute(stmt)
    all_users = result.scalars().all()

    # Re-rank: exact-start matches first
    starts = [u for u in all_users if u.full_name.lower().startswith(q.lower())]
    rest = [u for u in all_users if u not in starts]
    return (starts + rest)[:limit]
