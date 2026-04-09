"""Submissions API — full lifecycle management."""

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.task import Task, Submission
from app.schemas.tasks import (
    CreateSubmissionRequest, UpdateSubmissionRequest,
    SubmissionResponse, PaginatedSubmissionsResponse,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _to_response(sub: Submission, include_task: bool = False) -> SubmissionResponse:
    data = {
        "id": sub.id,
        "task_id": sub.task_id,
        "candidate_id": sub.candidate_id,
        "status": sub.status,
        "text_content": sub.text_content,
        "code_content": sub.code_content,
        "code_language": sub.code_language,
        "file_urls": sub.file_urls,
        "link_url": sub.link_url,
        "recording_url": sub.recording_url,
        "notes": sub.notes,
        "submitted_at": sub.submitted_at,
        "score_accuracy": sub.score_accuracy,
        "score_approach": sub.score_approach,
        "score_completeness": sub.score_completeness,
        "score_efficiency": sub.score_efficiency,
        "total_score": sub.total_score,
        "rank": sub.rank,
        "percentile": sub.percentile,
        "recruiter_feedback": sub.recruiter_feedback,
        "ai_summary": sub.ai_summary,
        "time_spent_minutes": sub.time_spent_minutes,
        "is_shortlisted": sub.is_shortlisted,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
        "task": None,
    }
    return SubmissionResponse(**data)


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: CreateSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    # Check task exists
    task_result = await db.execute(
        select(Task).where(Task.id == payload.task_id, Task.is_active == True)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Role separation: recruiter cannot submit to their own task
    if task.recruiter_id == current_user.id:
        raise HTTPException(status_code=403, detail="Recruiters cannot submit to their own tasks.")

    # Check deadline
    if task.deadline < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Deadline has passed.")

    # Check duplicate
    existing = await db.execute(
        select(Submission).where(
            Submission.task_id == payload.task_id,
            Submission.candidate_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already submitted for this task.")

    sub = Submission(
        task_id=payload.task_id,
        candidate_id=current_user.id,
        status="draft",
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return _to_response(sub)


@router.get("/my", response_model=PaginatedSubmissionsResponse)
async def get_my_submissions(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
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

    return PaginatedSubmissionsResponse(
        items=[_to_response(s) for s in subs],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(subs)) < total,
    )


@router.get("/{id}", response_model=SubmissionResponse)
async def get_submission(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    result = await db.execute(select(Submission).where(Submission.id == id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if sub.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return _to_response(sub)


@router.put("/{id}", response_model=SubmissionResponse)
async def update_submission(
    id: UUID,
    payload: UpdateSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    result = await db.execute(select(Submission).where(Submission.id == id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if sub.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if sub.status != "draft":
        raise HTTPException(status_code=403, detail="Cannot edit a submitted submission.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(sub, field, value)

    await db.flush()
    await db.refresh(sub)
    return _to_response(sub)


@router.post("/{id}/submit", response_model=SubmissionResponse)
async def submit_submission(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    result = await db.execute(select(Submission).where(Submission.id == id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if sub.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if sub.status != "draft":
        raise HTTPException(status_code=400, detail="Submission is not in draft status.")

    # Check deadline
    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if task and task.deadline < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Deadline has passed.")

    sub.status = "submitted"
    sub.submitted_at = datetime.utcnow()

    # Increment task submission count
    if task:
        task.submission_count = (task.submission_count or 0) + 1

    await db.flush()

    # Part 4: duplicate content check
    try:
        from backend.integrity.duplicate_checker import check_duplicate_and_flag
        await check_duplicate_and_flag(db, sub)
    except Exception:
        pass

    # Notify recruiter of new submission
    try:
        from app.services.notification_service import notify_new_submission
        from backend.notifications.fcm_service import push_new_submission
        if task:
            await notify_new_submission(
                db=db, recruiter_id=task.recruiter_id, task_id=task.id,
                task_title=task.title, submission_id=sub.id,
            )
            await push_new_submission(
                db, task.recruiter_id, task.title, task.id,
                task.submission_count or 1,
            )
    except Exception:
        pass

    await db.refresh(sub)
    return _to_response(sub)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Submission).where(Submission.id == id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if sub.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if sub.status != "draft":
        raise HTTPException(status_code=403, detail="Can only delete draft submissions.")
    await db.delete(sub)
    await db.flush()
