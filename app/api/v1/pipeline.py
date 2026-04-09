"""Pipeline API — manage candidate stages: shortlisted → hired."""

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter, get_current_user
from app.models.user import User, CandidateProfile
from app.models.task import Task, Submission
from app.models.recruiter import PipelineEntry, RecruiterAnalytics
from app.schemas.recruiter import (
    PipelineEntryResponse, PipelineBoardResponse,
    UpdatePipelineStageRequest, UpdatePipelineNotesRequest,
)
from app.services.notification_service import notify_stage_changed

router = APIRouter(prefix="/recruiter/pipeline", tags=["pipeline"])

VALID_STAGES = ["shortlisted", "interviewing", "offer_sent", "hired", "rejected"]


async def _build_entry_response(entry: PipelineEntry, db: AsyncSession) -> PipelineEntryResponse:
    # Candidate info
    user_result = await db.execute(
        select(User, CandidateProfile)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(User.id == entry.candidate_id)
    )
    row = user_result.first()
    candidate_name = None
    candidate_avatar = None
    if row:
        user_obj, profile_obj = row
        is_public = getattr(profile_obj, "public_profile", True) if profile_obj else True
        if is_public:
            candidate_name = user_obj.full_name
            candidate_avatar = user_obj.avatar_url

    # Task info
    task_result = await db.execute(select(Task).where(Task.id == entry.task_id))
    task = task_result.scalar_one_or_none()

    # Submission score/rank
    sub_result = await db.execute(select(Submission).where(Submission.id == entry.submission_id))
    sub = sub_result.scalar_one_or_none()

    return PipelineEntryResponse(
        id=entry.id,
        recruiter_id=entry.recruiter_id,
        candidate_id=entry.candidate_id,
        candidate_name=candidate_name,
        candidate_avatar=candidate_avatar,
        task_id=entry.task_id,
        task_title=task.title if task else None,
        task_domain=task.domain if task else None,
        submission_id=entry.submission_id,
        total_score=sub.total_score if sub else None,
        rank=sub.rank if sub else None,
        stage=entry.stage,
        recruiter_notes=entry.recruiter_notes,
        stage_updated_at=entry.stage_updated_at,
        created_at=entry.created_at,
    )


@router.get("", response_model=PipelineBoardResponse)
async def get_pipeline_board(
    task_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PipelineBoardResponse:
    query = select(PipelineEntry).where(PipelineEntry.recruiter_id == current_user.id)
    if task_id:
        query = query.where(PipelineEntry.task_id == task_id)
    query = query.order_by(PipelineEntry.stage_updated_at.desc())

    result = await db.execute(query)
    entries = result.scalars().all()

    board: dict[str, list] = {s: [] for s in VALID_STAGES}
    for entry in entries:
        stage = entry.stage
        if stage in board:
            board[stage].append(await _build_entry_response(entry, db))

    return PipelineBoardResponse(
        shortlisted=board["shortlisted"],
        interviewing=board["interviewing"],
        offer_sent=board["offer_sent"],
        hired=board["hired"],
        rejected=board["rejected"],
    )


@router.put("/{entry_id}/stage", response_model=PipelineEntryResponse)
async def update_stage(
    entry_id: UUID,
    payload: UpdatePipelineStageRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PipelineEntryResponse:
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {VALID_STAGES}")

    result = await db.execute(select(PipelineEntry).where(PipelineEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry or entry.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pipeline entry not found.")

    old_stage = entry.stage
    entry.stage = payload.stage
    entry.stage_updated_at = datetime.utcnow()

    # If hired, update analytics
    if payload.stage == "hired":
        analytics_result = await db.execute(
            select(RecruiterAnalytics).where(RecruiterAnalytics.task_id == entry.task_id)
        )
        analytics = analytics_result.scalar_one_or_none()
        if analytics:
            analytics.hired_count = (analytics.hired_count or 0) + 1

    await db.flush()

    # Get task for notification
    task_result = await db.execute(select(Task).where(Task.id == entry.task_id))
    task = task_result.scalar_one_or_none()
    if task:
        await notify_stage_changed(
            db=db,
            candidate_id=entry.candidate_id,
            task_id=task.id,
            task_title=task.title,
            stage=payload.stage,
            pipeline_id=entry.id,
        )
        # FCM push for stage change
        try:
            from backend.notifications.fcm_service import push_stage_changed, push_hired
            if payload.stage == "hired":
                await push_hired(db, entry.candidate_id, task.title, task.id)
            else:
                await push_stage_changed(db, entry.candidate_id, task.title, payload.stage, entry.id)
        except Exception:
            pass

    return await _build_entry_response(entry, db)


@router.put("/{entry_id}/notes", response_model=PipelineEntryResponse)
async def update_notes(
    entry_id: UUID,
    payload: UpdatePipelineNotesRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PipelineEntryResponse:
    result = await db.execute(select(PipelineEntry).where(PipelineEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry or entry.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pipeline entry not found.")

    entry.recruiter_notes = payload.recruiter_notes
    await db.flush()
    return await _build_entry_response(entry, db)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_pipeline(
    entry_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(PipelineEntry).where(PipelineEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry or entry.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pipeline entry not found.")
    await db.delete(entry)
    await db.flush()


# ── Candidate-facing pipeline view ───────────────────────────────────────────

candidate_pipeline_router = APIRouter(prefix="/candidate/pipeline", tags=["candidate-pipeline"])


@candidate_pipeline_router.get("")
async def get_my_pipeline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Candidate's own pipeline entries — all stages they are in."""
    result = await db.execute(
        select(PipelineEntry)
        .where(PipelineEntry.candidate_id == current_user.id)
        .order_by(PipelineEntry.stage_updated_at.desc())
    )
    entries = result.scalars().all()

    items = []
    for entry in entries:
        task_result = await db.execute(select(Task).where(Task.id == entry.task_id))
        task = task_result.scalar_one_or_none()

        sub_result = await db.execute(select(Submission).where(Submission.id == entry.submission_id))
        sub = sub_result.scalar_one_or_none()

        items.append({
            "id": str(entry.id),
            "task_id": str(entry.task_id),
            "task_title": task.title if task else None,
            "task_domain": task.domain if task else None,
            "submission_id": str(entry.submission_id),
            "total_score": sub.total_score if sub else None,
            "rank": sub.rank if sub else None,
            "stage": entry.stage,
            "stage_updated_at": entry.stage_updated_at.isoformat(),
            "created_at": entry.created_at.isoformat(),
        })

    return items
