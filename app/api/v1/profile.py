"""Profile API — POW profile, skill scores, badges, task history."""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, CandidateProfile
from app.models.task import Submission
from app.schemas.tasks import (
    POWProfileResponse, ProfileStatsResponse, SkillScoreResponse,
    SkillScoreHistoryItem, BadgeResponse, SubmissionResponse,
    PaginatedSubmissionsResponse,
)
from app.services.skill_score_service import seed_skill_scores, get_skill_scores
from app.services.badge_service import compute_earned_badges

router = APIRouter(prefix="/profile", tags=["profile"])


async def _build_pow_profile(user: User, db: AsyncSession) -> POWProfileResponse:
    # Stats
    subs_result = await db.execute(
        select(Submission).where(Submission.candidate_id == user.id)
    )
    all_subs = subs_result.scalars().all()

    attempted = len(all_subs)
    completed = sum(1 for s in all_subs if s.status in ("submitted", "under_review", "scored"))
    scored_subs = [s for s in all_subs if s.status == "scored" and s.total_score is not None]
    tasks_scored = len(scored_subs)
    best_rank = min((s.rank for s in scored_subs if s.rank), default=None)
    avg_score = (
        round(sum(s.total_score for s in scored_subs) / tasks_scored, 1)
        if tasks_scored else None
    )
    top_10 = sum(1 for s in scored_subs if s.percentile is not None and s.percentile >= 90)

    stats = ProfileStatsResponse(
        tasks_attempted=attempted,
        tasks_completed=completed,
        tasks_scored=tasks_scored,
        best_rank=best_rank,
        average_score=avg_score,
        top_10_percent_finishes=top_10,
    )

    # Skill score
    score_data = await get_skill_scores(user.id, db)
    skill_score = SkillScoreResponse(
        overall=score_data["overall"],
        domains=score_data["domains"],
        percentile=score_data["percentile"],
        history=[
            SkillScoreHistoryItem(
                domain=h.domain,
                score=h.score,
                delta=h.delta,
                reason=h.reason,
                created_at=h.created_at,
            )
            for h in score_data["history"]
        ],
    )

    # Badges
    badge_data = await compute_earned_badges(user.id, db)
    badges = [BadgeResponse(**b) for b in badge_data]

    # Recent submissions (last 10)
    recent_result = await db.execute(
        select(Submission)
        .where(
            Submission.candidate_id == user.id,
            Submission.status.in_(["submitted", "under_review", "scored"]),
        )
        .order_by(Submission.updated_at.desc())
        .limit(10)
    )
    recent_subs = recent_result.scalars().all()

    def _sub_to_resp(s: Submission) -> SubmissionResponse:
        return SubmissionResponse(
            id=s.id, task_id=s.task_id, candidate_id=s.candidate_id,
            status=s.status, text_content=s.text_content, code_content=s.code_content,
            code_language=s.code_language, file_urls=s.file_urls, link_url=s.link_url,
            recording_url=s.recording_url, notes=s.notes, submitted_at=s.submitted_at,
            score_accuracy=s.score_accuracy, score_approach=s.score_approach,
            score_completeness=s.score_completeness, score_efficiency=s.score_efficiency,
            total_score=s.total_score, rank=s.rank, percentile=s.percentile,
            recruiter_feedback=s.recruiter_feedback, ai_summary=s.ai_summary,
            time_spent_minutes=s.time_spent_minutes, is_shortlisted=s.is_shortlisted,
            created_at=s.created_at, updated_at=s.updated_at,
        )

    profile = user.candidate_profile
    profile_dict = {}
    if profile:
        profile_dict = {
            "headline": profile.headline, "bio": profile.bio, "city": profile.city,
            "github_url": profile.github_url, "linkedin_url": profile.linkedin_url,
            "portfolio_url": profile.portfolio_url, "skill_tags": profile.skill_tags or [],
            "career_goal": profile.career_goal, "skill_score": profile.skill_score,
            "public_profile": getattr(profile, "public_profile", True),
        }

    return POWProfileResponse(
        user={
            "id": str(user.id), "email": user.email, "full_name": user.full_name,
            "avatar_url": user.avatar_url, "role": user.role,
        },
        profile=profile_dict,
        stats=stats,
        skill_score=skill_score,
        badges=badges,
        recent_submissions=[_sub_to_resp(s) for s in recent_subs],
    )


@router.get("/me", response_model=POWProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> POWProfileResponse:
    result = await db.execute(
        select(User).where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return await _build_pow_profile(user, db)


@router.get("/me/task-history", response_model=PaginatedSubmissionsResponse)
async def get_task_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedSubmissionsResponse:
    query = select(Submission).where(Submission.candidate_id == current_user.id)
    if status_filter:
        query = query.where(Submission.status == status_filter)
    query = query.order_by(Submission.updated_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    subs = result.scalars().all()

    def _sub_to_resp(s: Submission) -> SubmissionResponse:
        return SubmissionResponse(
            id=s.id, task_id=s.task_id, candidate_id=s.candidate_id,
            status=s.status, text_content=s.text_content, code_content=s.code_content,
            code_language=s.code_language, file_urls=s.file_urls, link_url=s.link_url,
            recording_url=s.recording_url, notes=s.notes, submitted_at=s.submitted_at,
            score_accuracy=s.score_accuracy, score_approach=s.score_approach,
            score_completeness=s.score_completeness, score_efficiency=s.score_efficiency,
            total_score=s.total_score, rank=s.rank, percentile=s.percentile,
            recruiter_feedback=s.recruiter_feedback, ai_summary=s.ai_summary,
            time_spent_minutes=s.time_spent_minutes, is_shortlisted=s.is_shortlisted,
            created_at=s.created_at, updated_at=s.updated_at,
        )

    return PaginatedSubmissionsResponse(
        items=[_sub_to_resp(s) for s in subs],
        total=total, page=page, page_size=page_size,
        has_more=(offset + len(subs)) < total,
    )


@router.get("/{user_id}", response_model=POWProfileResponse)
async def get_public_profile(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> POWProfileResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return await _build_pow_profile(user, db)


router_scores = APIRouter(prefix="/scores", tags=["scores"])


@router_scores.get("/me", response_model=SkillScoreResponse)
async def get_my_scores(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SkillScoreResponse:
    score_data = await get_skill_scores(current_user.id, db)
    return SkillScoreResponse(
        overall=score_data["overall"],
        domains=score_data["domains"],
        percentile=score_data["percentile"],
        history=[
            SkillScoreHistoryItem(
                domain=h.domain, score=h.score, delta=h.delta,
                reason=h.reason, created_at=h.created_at,
            )
            for h in score_data["history"]
        ],
    )


@router_scores.post("/seed", status_code=204)
async def seed_scores(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await seed_skill_scores(current_user.id, db)


router_badges = APIRouter(prefix="/badges", tags=["badges"])


@router_badges.get("/me", response_model=list[BadgeResponse])
async def get_my_badges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BadgeResponse]:
    badge_data = await compute_earned_badges(current_user.id, db)
    return [BadgeResponse(**b) for b in badge_data]
