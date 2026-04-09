"""Recruiter Analytics API — task performance metrics."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.models.user import User
from app.models.task import Task, Submission
from app.models.recruiter import RecruiterAnalytics, PipelineEntry
from app.schemas.recruiter import AnalyticsResponse, SubmissionTimelinePoint

router = APIRouter(prefix="/recruiter/analytics", tags=["recruiter-analytics"])


async def _build_analytics(
    db: AsyncSession,
    task: Task,
    recruiter_id: UUID,
) -> AnalyticsResponse:
    analytics_result = await db.execute(
        select(RecruiterAnalytics).where(RecruiterAnalytics.task_id == task.id)
    )
    analytics = analytics_result.scalar_one_or_none()

    # Submission timeline (daily counts from publish to deadline)
    timeline: list[SubmissionTimelinePoint] = []
    subs_result = await db.execute(
        select(Submission).where(
            Submission.task_id == task.id,
            Submission.submitted_at.isnot(None),
        ).order_by(Submission.submitted_at.asc())
    )
    all_subs = subs_result.scalars().all()

    if all_subs:
        start = all_subs[0].submitted_at.date()
        end = datetime.utcnow().date()
        day = start
        while day <= end:
            count = sum(
                1 for s in all_subs
                if s.submitted_at and s.submitted_at.date() == day
            )
            timeline.append(SubmissionTimelinePoint(date=day.isoformat(), count=count))
            day += timedelta(days=1)

    # Pipeline funnel
    shortlisted_result = await db.execute(
        select(func.count()).where(
            PipelineEntry.task_id == task.id,
            PipelineEntry.recruiter_id == recruiter_id,
        )
    )
    shortlisted = shortlisted_result.scalar() or 0

    hired_result = await db.execute(
        select(func.count()).where(
            PipelineEntry.task_id == task.id,
            PipelineEntry.recruiter_id == recruiter_id,
            PipelineEntry.stage == "hired",
        )
    )
    hired = hired_result.scalar() or 0

    total_subs = len(all_subs)
    scored = sum(1 for s in all_subs if s.status == "scored")
    conversion = round((total_subs / max(task.view_count, 1)) * 100, 1) if task.view_count else None

    if analytics:
        return AnalyticsResponse(
            task_id=task.id,
            total_views=analytics.total_views or task.view_count,
            total_submissions=analytics.total_submissions or total_subs,
            scored_count=analytics.scored_count or scored,
            shortlisted_count=analytics.shortlisted_count or shortlisted,
            hired_count=analytics.hired_count or hired,
            avg_score=analytics.avg_score,
            score_distribution=analytics.score_distribution,
            avg_time_spent_mins=analytics.avg_time_spent_mins,
            time_to_first_submission_hours=analytics.time_to_first_submission_hours,
            conversion_rate=conversion,
            submission_timeline=timeline,
        )

    return AnalyticsResponse(
        task_id=task.id,
        total_views=task.view_count,
        total_submissions=total_subs,
        scored_count=scored,
        shortlisted_count=shortlisted,
        hired_count=hired,
        avg_score=None,
        score_distribution=None,
        avg_time_spent_mins=None,
        time_to_first_submission_hours=None,
        conversion_rate=conversion,
        submission_timeline=timeline,
    )


@router.get("", response_model=AnalyticsResponse)
async def get_aggregate_analytics(
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    tasks_result = await db.execute(
        select(Task).where(Task.recruiter_id == current_user.id, Task.is_published == True)
    )
    tasks = tasks_result.scalars().all()

    if not tasks:
        return AnalyticsResponse(
            total_views=0, total_submissions=0, scored_count=0,
            shortlisted_count=0, hired_count=0, submission_timeline=[],
        )

    total_views = sum(t.view_count or 0 for t in tasks)
    total_subs = sum(t.submission_count or 0 for t in tasks)

    analytics_result = await db.execute(
        select(RecruiterAnalytics).where(
            RecruiterAnalytics.task_id.in_([t.id for t in tasks])
        )
    )
    all_analytics = analytics_result.scalars().all()

    scored = sum(a.scored_count or 0 for a in all_analytics)
    shortlisted = sum(a.shortlisted_count or 0 for a in all_analytics)
    hired = sum(a.hired_count or 0 for a in all_analytics)

    scores = [a.avg_score for a in all_analytics if a.avg_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    return AnalyticsResponse(
        total_views=total_views,
        total_submissions=total_subs,
        scored_count=scored,
        shortlisted_count=shortlisted,
        hired_count=hired,
        avg_score=avg_score,
        submission_timeline=[],
    )


@router.get("/{task_id}", response_model=AnalyticsResponse)
async def get_task_analytics(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")

    return await _build_analytics(db, task, current_user.id)
