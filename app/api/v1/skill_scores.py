"""Skill Score API v2 — Part 4."""

from uuid import UUID
import sqlalchemy

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, CandidateProfile
from app.models.part4 import SkillScoreSnapshot

router = APIRouter(prefix="/scores", tags=["skill-scores"])

TIER_MAP = [
    (950, "Elite", "#8B5CF6"),
    (800, "Expert", "#E94560"),
    (600, "Advanced", "#F59E0B"),
    (400, "Proficient", "#10B981"),
    (200, "Developing", "#3B82F6"),
    (0, "Beginner", "#6B7280"),
]


def _get_tier(score: int) -> dict:
    for threshold, label, color in TIER_MAP:
        if score >= threshold:
            return {"label": label, "color": color}
    return {"label": "Beginner", "color": "#6B7280"}


def _snapshot_to_dict(snap: SkillScoreSnapshot) -> dict:
    return {
        "id": str(snap.id),
        "overall_score": snap.overall_score,
        "domain_scores": snap.domain_scores,
        "percentile_overall": snap.percentile_overall,
        "percentile_by_domain": snap.percentile_by_domain,
        "snapshot_reason": snap.snapshot_reason,
        "submission_id": str(snap.submission_id) if snap.submission_id else None,
        "hash": snap.hash,
        "created_at": snap.created_at.isoformat(),
    }


@router.get("/me/detail")
async def get_my_skill_score_detail(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    overall = profile.skill_score if profile else 0
    domain_scores = profile.scores if profile else {}
    percentile = round((overall / 1000) * 100, 1) if overall else 0.0

    snaps_result = await db.execute(
        select(SkillScoreSnapshot)
        .where(SkillScoreSnapshot.candidate_id == current_user.id)
        .order_by(SkillScoreSnapshot.created_at.desc())
        .limit(20)
    )
    snapshots = snaps_result.scalars().all()
    tier = _get_tier(overall)

    return {
        "overall_score": overall,
        "domain_scores": domain_scores or {},
        "percentile_overall": percentile,
        "percentile_by_domain": {d: round((s / 1000) * 100, 1) for d, s in (domain_scores or {}).items()},
        "tier": tier,
        "snapshots": [_snapshot_to_dict(s) for s in snapshots],
    }


@router.get("/{user_id}/public")
async def get_public_score(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    overall = profile.skill_score or 0
    domain_scores = profile.scores or {}
    return {
        "user_id": str(user_id),
        "overall_score": overall,
        "tier": _get_tier(overall),
        "domain_tiers": {d: _get_tier(s) for d, s in domain_scores.items()},
        "percentile_overall": round((overall / 1000) * 100, 1),
    }


@router.get("/leaderboard/global")
async def global_leaderboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(CandidateProfile.skill_score > 0)
        .order_by(CandidateProfile.skill_score.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    entries = []
    for i, (user, profile) in enumerate(rows):
        rank = (page - 1) * page_size + i + 1
        entries.append({
            "rank": rank,
            "user_id": str(user.id),
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "overall_score": profile.skill_score,
            "tier": _get_tier(profile.skill_score),
            "is_current_user": user.id == current_user.id,
        })
    return {"entries": entries, "page": page, "page_size": page_size}


@router.get("/leaderboard/{domain}")
async def domain_leaderboard(
    domain: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(CandidateProfile.scores.op("?")(domain))
        .order_by(
            CandidateProfile.scores.op("->>")(domain).cast(sqlalchemy.Integer).desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    entries = []
    for i, (user, profile) in enumerate(rows):
        rank = (page - 1) * page_size + i + 1
        domain_score = (profile.scores or {}).get(domain, 0)
        entries.append({
            "rank": rank,
            "user_id": str(user.id),
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "domain_score": domain_score,
            "tier": _get_tier(domain_score),
            "is_current_user": user.id == current_user.id,
        })
    return {"domain": domain, "entries": entries, "page": page, "page_size": page_size}
